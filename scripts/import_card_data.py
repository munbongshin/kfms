"""
Import the corporate-card sample workbook into a single flat table.

The data workbook stacks several source tables vertically on one sheet: an
optional row holding only the table name, a header row, the rows, then a blank
separator. Every block is folded into one table whose columns are the union of
all block headers, with source_table marking which block a row came from.
Column types and Korean comments come from the table-definition workbook.
"""
import os
import re
import sys

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

DATA_FILE = os.environ.get(
    "CARD_DATA_FILE",
    r"C:\Users\신문봉-PC\Desktop\2026\교육\새 폴더\KFMS_매뉴얼\card data .xlsx",
)
SPEC_FILE = os.environ.get(
    "CARD_SPEC_FILE",
    r"C:\Users\신문봉-PC\Desktop\2026\교육\새 폴더\KFMS_매뉴얼"
    r"\법인카드 테이블 정보 정리_20260911_v1.0.xlsx",
)
SPEC_SHEET = "테이블 상세"
TABLE = os.environ.get("CARD_TABLE", "card_data")
DROP_PREFIX = "cats_"

# One view per source block, exposing only that block's columns, so callers can
# query a single entity without repeating the source_table filter.
VIEWS = {
    "CATS_TMP_CARDINFO": "v_card_info",
    "CATS_RTUN_HIST": "v_card_dept",
    "CATS_TMP_ACQUIRE": "v_acquire",
    "CATS_TMP_APPROVAL": "v_approval",
    "CATS_TMP_BILL": "v_bill",
}

DB = dict(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", 5434)),
    dbname=os.environ.get("DB_NAME", "retail"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "postgres"),
)

NULL_TOKEN = "[NULL]"


def load_specs():
    sheet = pd.read_excel(SPEC_FILE, sheet_name=SPEC_SHEET, header=None)
    heads = [i for i in range(len(sheet)) if str(sheet.iat[i, 0]).startswith("(")]
    specs = {}
    for n, start in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(sheet)
        name = re.sub(r"^\(\d+\)\s*", "", str(sheet.iat[start, 0])).strip()
        columns = []
        for row in range(start + 2, end):
            col = str(sheet.iat[row, 0]).strip()
            if col in ("nan", ""):
                continue
            columns.append(
                {
                    "name": col,
                    "type": str(sheet.iat[row, 2]).strip(),
                    "comment": str(sheet.iat[row, 6]).strip(),
                }
            )
        specs.setdefault(name, {"title": str(sheet.iat[start, 1]).strip(), "columns": columns})
    return specs


def load_blocks():
    """Split the sheet into (header, frame) blocks; the first may lack a title row."""
    sheet = pd.read_excel(DATA_FILE, sheet_name=0, header=None, dtype=str)
    titles = [
        i
        for i in range(len(sheet))
        if sheet.iloc[i].notna().sum() == 1 and str(sheet.iat[i, 0]).strip() not in ("nan", "")
    ]
    starts = titles if titles and titles[0] == 0 else [0] + titles
    blocks = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(sheet)
        head_row = start + 1 if start in titles else start
        header = [str(x).strip() for x in sheet.iloc[head_row].tolist() if str(x).strip() not in ("nan", "")]
        frame = sheet.iloc[head_row + 1 : end, : len(header)].dropna(how="all").copy()
        frame.columns = header
        blocks.append(frame)
    return blocks


def identify(frame, specs):
    header = list(frame.columns)
    for name, spec in specs.items():
        if [c["name"] for c in spec["columns"]] == header:
            return name
    return None


TYPE_RANK = {"CHAR": 0, "VARCHAR": 1}


def pg_type(oracle_type):
    m = re.fullmatch(r"VARCHAR2\((\d+)\)", oracle_type)
    if m:
        return "VARCHAR", int(m.group(1))
    m = re.fullmatch(r"CHAR\((\d+)\)", oracle_type)
    if m:
        return "CHAR", int(m.group(1))
    m = re.fullmatch(r"NUMBER\((\d+),(\d+)\)", oracle_type)
    if m:
        return "NUMERIC", (int(m.group(1)), int(m.group(2)))
    raise ValueError("unmapped type: %s" % oracle_type)


def widen(a, b):
    """Reconcile a column declared differently in two source tables."""
    if a is None:
        return b
    (ka, sa), (kb, sb) = a, b
    if ka == "NUMERIC" or kb == "NUMERIC":
        return a if ka == "NUMERIC" else b
    kind = "VARCHAR" if "VARCHAR" in (ka, kb) else "CHAR"
    return kind, max(sa, sb)


def render(kind, size):
    return "%s(%d,%d)" % (kind, *size) if kind == "NUMERIC" else "%s(%d)" % (kind, size)


def build_columns(blocks, specs, names):
    """Union of every block's columns, in first-appearance order."""
    order = []
    types = {}
    comments = {}
    for frame, name in zip(blocks, names):
        for col in specs[name]["columns"]:
            if col["name"] not in types:
                order.append(col["name"])
                comments[col["name"]] = col["comment"]
            types[col["name"]] = widen(types.get(col["name"]), pg_type(col["type"]))
    return order, types, comments


def clean(frame, types):
    out = frame.replace({NULL_TOKEN: None})
    out = out.where(out.notna(), None)
    for name in out.columns:
        series = out[name].map(lambda v: None if v is None or str(v).strip() == "" else str(v).strip())
        if types[name][0] == "NUMERIC":
            series = series.map(lambda v: None if v is None else v.replace(",", ""))
        out[name] = series
    return out


def check(source, frame, types):
    problems = []
    for name in frame.columns:
        present = frame[name][frame[name].notna()]
        if not len(present):
            continue
        kind, size = types[name]
        if kind in TYPE_RANK and present.map(len).max() > size:
            problems.append(
                "%s.%s exceeds %s (actual %d)" % (source, name, render(kind, size), present.map(len).max())
            )
        if kind == "NUMERIC":
            bad = present[~present.str.fullmatch(r"-?\d+(\.\d+)?")]
            if len(bad):
                problems.append("%s.%s not numeric: %r" % (source, name, bad.head(3).tolist()))
    return problems


def sql_str(value):
    return "'%s'" % value.replace("'", "''")


def main():
    specs = load_specs()
    blocks = load_blocks()

    names = [identify(f, specs) for f in blocks]
    unknown = [i for i, n in enumerate(names) if n is None]
    if unknown:
        print("Could not match block(s) %r to any table spec" % unknown)
        return 1

    order, types, comments = build_columns(blocks, specs, names)

    prepared = []
    problems = []
    for frame, name in zip(blocks, names):
        frame = clean(frame, types)
        problems.extend(check(name, frame, types))
        prepared.append((name, frame))

    if problems:
        sys.stdout.buffer.write(("Validation failed:\n  " + "\n  ".join(problems) + "\n").encode("utf-8"))
        return 1

    cols = [c.lower() for c in order]
    body = ",\n".join("    %s %s" % (c.lower(), render(*types[c])) for c in order)
    statements = [
        "CREATE TABLE %s (\n    source_table VARCHAR(30) NOT NULL,\n%s\n);" % (TABLE, body),
        "COMMENT ON TABLE %s IS %s;" % (TABLE, sql_str("법인카드 통합 데이터 (원천 테이블 5종 통합)")),
        "COMMENT ON COLUMN %s.source_table IS %s;" % (TABLE, sql_str("원천 테이블명")),
    ] + [
        "COMMENT ON COLUMN %s.%s IS %s;" % (TABLE, c.lower(), sql_str(comments[c]))
        for c in order
        if comments[c] and comments[c] != "nan"
    ]

    insert = "INSERT INTO %s (source_table, %s) VALUES (%s)" % (
        TABLE,
        ", ".join(cols),
        ", ".join(["%s"] * (len(cols) + 1)),
    )

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select tablename from pg_tables where schemaname='public' and tablename like %s",
                (DROP_PREFIX + "%",),
            )
            stale = [r[0] for r in cur.fetchall()]
            for table in stale:
                cur.execute("DROP TABLE IF EXISTS %s" % table)
            if stale:
                print("dropped: %s" % ", ".join(stale))

            cur.execute("DROP TABLE IF EXISTS %s CASCADE" % TABLE)
            for statement in statements:
                cur.execute(statement)

            total = 0
            for name, frame in prepared:
                present = list(frame.columns)
                rows = [
                    (name,) + tuple(row.get(c) for c in order)
                    for row in (dict(zip(present, r)) for r in frame.itertuples(index=False, name=None))
                ]
                execute_batch(cur, insert, rows, page_size=500)
                total += len(rows)
                sys.stdout.buffer.write(("  %-20s %d rows\n" % (name, len(rows))).encode("utf-8"))
            print("%s: %d columns, %d rows" % (TABLE, len(cols) + 1, total))

            for name, view in VIEWS.items():
                view_cols = ", ".join(c["name"].lower() for c in specs[name]["columns"])
                cur.execute(
                    "CREATE VIEW %s AS SELECT %s FROM %s WHERE source_table = %s"
                    % (view, view_cols, TABLE, sql_str(name))
                )
                cur.execute("COMMENT ON VIEW %s IS %s" % (view, sql_str(specs[name]["title"])))
                sys.stdout.buffer.write(
                    ("  %-14s -> %s\n" % (view, specs[name]["title"])).encode("utf-8")
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
