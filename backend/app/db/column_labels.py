"""Display names for columns, managed by an administrator.

Nothing here is a fixed list of column names. A label comes from, in order:

1. an override for that table's column,
2. an override for that column name on the connection (covers a table and every
   view that reuses the name, so it is entered once),
3. the column's own DB comment.

Overrides live in the KFMS metadata database. The catalog read from the target
database stays cached and untouched; labels are laid over a copy per request, so
a change shows at once without re-reading the target.
"""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# What a computed column is called when nobody chose otherwise: SUM(appramt)
# reads "승인금액 합계". An administrator can rename any of them; this is only
# the starting point and what "기본값으로" returns to.
DEFAULT_EXPRESSION_TERMS: Dict[str, str] = {
    "sum": "합계",
    "count": "건수",
    "avg": "평균",
    "max": "최대값",
    "min": "최소값",
    "?column?": "계산값",  # what PostgreSQL names an unaliased expression
}


@dataclass(frozen=True)
class Override:
    """`table_key` None means the column name on the whole connection."""
    table_key: Optional[str]
    column_name: str
    label: str
    id: Optional[int] = None


def _clean(overrides: Iterable[Override]) -> List[Override]:
    return [o for o in overrides if o.label and o.label.strip()]


def _lookups(overrides: Iterable[Override]) -> Tuple[Dict[Tuple[str, str], str], Dict[str, str]]:
    by_table: Dict[Tuple[str, str], str] = {}
    wide: Dict[str, str] = {}
    for o in _clean(overrides):
        if o.table_key is None:
            wide[o.column_name] = o.label.strip()
        else:
            by_table[(o.table_key, o.column_name)] = o.label.strip()
    return by_table, wide


def apply_labels(
    schema: Mapping[str, Sequence[Mapping[str, Any]]], overrides: Iterable[Override]
) -> Dict[str, List[Dict[str, Any]]]:
    """A copy of the schema where each column has `label` and `label_source`.

    The comment is left whole: tooltips show it, and it is not what users say.
    """
    by_table, wide = _lookups(overrides)
    result: Dict[str, List[Dict[str, Any]]] = {}
    for table, columns in schema.items():
        result[table] = []
        for column in columns:
            name = column["name"]
            comment = (column.get("comment") or "").strip() or None
            if (table, name) in by_table:
                label, source = by_table[(table, name)], "table"
            elif name in wide:
                label, source = wide[name], "connection"
            elif comment:
                label, source = comment, "comment"
            else:
                label, source = None, None
            result[table].append({**column, "label": label, "label_source": source})
    return result


def coverage(
    schema: Mapping[str, Sequence[Mapping[str, Any]]], overrides: Iterable[Override]
) -> List[Dict[str, Any]]:
    """One row per distinct column name, for the management screen.

    `label` is what the name shows unless a table has its own exception, and
    `mapped` says whether it shows anything at all.
    """
    overrides = _clean(overrides)
    _, wide = _lookups(overrides)
    exceptions: Dict[str, List[Dict[str, Any]]] = {}
    for o in overrides:
        if o.table_key is not None:
            exceptions.setdefault(o.column_name, []).append(
                {"id": o.id, "table_key": o.table_key, "label": o.label.strip()}
            )

    rows: Dict[str, Dict[str, Any]] = {}
    for table, columns in schema.items():
        for column in columns:
            name = column["name"]
            row = rows.setdefault(name, {"name": name, "tables": [], "comment": None, "type": column.get("type")})
            row["tables"].append(table)
            row["comment"] = row["comment"] or (column.get("comment") or "").strip() or None

    # An override whose column has since disappeared stays visible so it can be removed.
    for name in {o.column_name for o in overrides} - rows.keys():
        rows[name] = {"name": name, "tables": [], "comment": None, "type": None}

    wide_ids = {o.column_name: o.id for o in overrides if o.table_key is None}
    out: List[Dict[str, Any]] = []
    for name, row in rows.items():
        if name in wide:
            label, source = wide[name], "connection"
        elif row["comment"]:
            label, source = row["comment"], "comment"
        else:
            label, source = None, None
        out.append({
            **row,
            "default_label": row["comment"],
            "label": label,
            "source": source,
            "mapped": label is not None,
            "exceptions": exceptions.get(name, []),
            "id": wide_ids.get(name),
        })
    return out


def merge_expression_terms(stored: Mapping[str, str]) -> List[Dict[str, Any]]:
    """Every computed-column term with its default and any administrator change."""
    terms = []
    for func, default in DEFAULT_EXPRESSION_TERMS.items():
        chosen = (stored.get(func) or "").strip()
        terms.append({
            "func": func,
            "label": chosen or default,
            "default": default,
            "customized": bool(chosen) and chosen != default,
        })
    return terms


# --- reading a sheet of names ---------------------------------------------------------------

_COLUMN_HEADERS = {"컬럼명", "컬럼", "영문명", "영문컬럼명", "column", "columnname", "field", "fieldname", "name"}
_LABEL_HEADERS = {"한글명", "한글컬럼명", "한글", "표시명", "라벨", "label", "displayname", "display", "korean"}
_TABLE_HEADERS = {"테이블", "테이블명", "table", "tablename"}


def _norm(value: Any) -> str:
    return "".join(str(value or "").lower().replace("_", "").split())


def parse_label_sheet(rows: Sequence[Sequence[Any]]) -> Tuple[List[Override], List[Dict[str, Any]]]:
    """Read (column name, Korean name[, table]) rows; the first row is the header.

    Columns are found by header text, in any order, so a definition workbook can
    be used as it is. Problems come back with their row number rather than
    stopping the whole sheet.
    """
    if not rows:
        return [], [{"row": 1, "reason": "빈 시트입니다"}]

    header = [_norm(h) for h in rows[0]]

    def find(names: set) -> Optional[int]:
        return next((i for i, h in enumerate(header) if h in names), None)

    col_i, label_i, table_i = find(_COLUMN_HEADERS), find(_LABEL_HEADERS), find(_TABLE_HEADERS)
    if col_i is None or label_i is None:
        return [], [{"row": 1, "reason": "헤더에서 '컬럼명'과 '한글명' 열을 찾지 못했습니다"}]

    def cell(row: Sequence[Any], i: Optional[int]) -> str:
        if i is None or i >= len(row) or row[i] is None:
            return ""
        return str(row[i]).strip()

    problems: List[Dict[str, Any]] = []
    latest: Dict[Tuple[Optional[str], str], Override] = {}
    for number, row in enumerate(rows[1:], start=2):
        name, label, table = cell(row, col_i), cell(row, label_i), cell(row, table_i)
        if not label:
            continue  # blank line, or a name not filled in yet (an export has many)
        if not name:
            problems.append({"row": number, "reason": "컬럼명이 없습니다"})
        elif len(label) > 100:
            problems.append({"row": number, "reason": "한글명이 100자를 넘습니다"})
        else:
            key = (table or None, name)
            latest.pop(key, None)  # the last row for a name wins
            latest[key] = Override(table or None, name, label)
    return list(latest.values()), problems
