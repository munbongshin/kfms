"""Korean column names only, for everyone but administrators.

English column names are technical identifiers. People who are not
administrators see the Korean names instead, and the server does the
converting — the schema, table previews, query results, saved results and
anomaly details all pass through here — so the English names are not in the
response at all, not merely hidden on screen.

A column with no Korean name of any kind (no override, no Korean comment, no
Korean physical name) is shown as "이름 미지정 1", "이름 미지정 2" ... until an
administrator names it.
"""
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.db.column_labels import has_korean  # noqa: F401 — re-exported

PLACEHOLDER = "이름 미지정"

_AGGREGATE = re.compile(
    r'\b(sum|count|avg|max|min)\s*\(\s*(?:distinct\s+)?((?:"?\w+"?\.)?"?\w+"?|\*)\s*\)(?:\s+as\s+("[^"]+"|\w+))?',
    re.IGNORECASE,
)
_ASCII_NAME = re.compile(r"^[\x20-\x7e]+$")


def _unique(name: str, seen: Dict[str, int]) -> str:
    """`name`, or `name (2)`, `name (3)` ... when it has been used already."""
    seen[name] = seen.get(name, 0) + 1
    return name if seen[name] == 1 else f"{name} ({seen[name]})"


def visible_schema(
    schema: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, str]]]:
    """The schema as a non-administrator gets it, and how to map a shown name back.

    `schema` is what apply_labels returned. Each column's `name` becomes its
    Korean name, made unique within its table; defaults and any comment that is
    not Korean are dropped.
    """
    visible: Dict[str, List[Dict[str, Any]]] = {}
    real_by_shown: Dict[str, Dict[str, str]] = {}
    for table, columns in schema.items():
        seen: Dict[str, int] = {}
        unnamed = 0
        visible[table], real_by_shown[table] = [], {}
        for column in columns:
            label = column.get("label")
            if label and has_korean(label):
                shown = _unique(label, seen)
            else:
                unnamed += 1
                shown = _unique(f"{PLACEHOLDER} {unnamed}", seen)
            comment = column.get("comment")
            visible[table].append({
                "name": shown,
                "type": column.get("type"),
                "nullable": column.get("nullable"),
                "default": None,
                "comment": comment if comment and has_korean(comment) else None,
                "label": shown,
            })
            real_by_shown[table][shown] = column["name"]
    return visible, real_by_shown


def _tables_read_by(sql: str, keys: Sequence[str]) -> List[str]:
    words = set(re.findall(r"[\w]+", sql.lower()))
    bare = lambda key: key.split(".")[-1].lower()
    read = [k for k in keys if bare(k) in words]
    return read + [k for k in keys if k not in read]


def result_labels(schema: Mapping[str, Sequence[Mapping[str, Any]]], sql: str) -> Dict[str, str]:
    """Column name -> Korean label for the columns a result may carry.

    A column can be named differently per table; the tables the SQL reads name
    it first. Only Korean labels are offered.
    """
    labels: Dict[str, str] = {}
    for table in _tables_read_by(sql or "", list(schema)):
        for column in schema[table]:
            label = column.get("label")
            if label and has_korean(label) and column["name"] not in labels:
                labels[column["name"]] = label
    return labels


def _bare(identifier: str) -> str:
    last = identifier.split(".")[-1]
    return last[1:-1] if last.startswith('"') else last.lower()


def labels_from_sql(sql: str, column_labels: Mapping[str, str], terms: Mapping[str, str]) -> Dict[str, str]:
    """Result column -> Korean name for the computed columns in `sql`:
    SUM(appramt) AS total_amt reads "승인금액 합계"."""
    labels: Dict[str, str] = {}
    for match in _AGGREGATE.finditer(sql or ""):
        fn, arg, alias = match.group(1).lower(), match.group(2), match.group(3)
        term = terms.get(fn)
        if not term:
            continue
        # Without AS, PostgreSQL names the column after the function.
        name = (alias[1:-1] if alias.startswith('"') else alias.lower()) if alias else fn
        if not _ASCII_NAME.match(name):  # a Korean alias already reads correctly
            continue
        subject = None if arg == "*" else column_labels.get(_bare(arg))
        labels[name] = f"{subject} {term}" if subject else term
    return labels


def relabel_rows(
    rows: Sequence[Mapping[str, Any]],
    sql: str,
    column_labels: Mapping[str, str],
    terms: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Rows with every column renamed to a Korean name; values are untouched."""
    if not rows:
        return []
    computed = labels_from_sql(sql, column_labels, terms)
    seen: Dict[str, int] = {}
    unnamed = 0
    mapping: Dict[str, str] = {}
    for key in rows[0].keys():
        label: Optional[str] = computed.get(key) or column_labels.get(key)
        if not label and has_korean(key):
            label = key
        if not label:
            label = terms.get(key)  # PostgreSQL's own names: sum, count, ?column?
        if not label:
            unnamed += 1
            label = f"{PLACEHOLDER} {unnamed}"
        mapping[key] = _unique(label, seen)
    return [{mapping[k]: v for k, v in row.items()} for row in rows]


def anonymize_detail(detail: Mapping[str, Any], labels: Mapping[str, str]) -> Dict[str, Any]:
    """One anomaly transaction's detail with Korean field names only."""
    seen: Dict[str, int] = {}
    unnamed = 0

    def shown(item: Mapping[str, Any]) -> str:
        nonlocal unnamed
        label = item.get("label") or ""
        if not has_korean(label):
            label = labels.get(item.get("field", ""), "")
        if not has_korean(label):
            unnamed += 1
            label = f"{PLACEHOLDER} {unnamed}"
        return _unique(label, seen)

    out = dict(detail)
    for group in ("core", "rest"):
        renamed = []
        for item in detail.get(group, []):
            name = shown(item)
            renamed.append({"field": name, "label": name, "value": item.get("value")})
        out[group] = renamed
    return out


def to_real(shown: Sequence[str], real_by_shown: Mapping[str, str]) -> List[str]:
    """Real column names for names a non-administrator was shown.

    A name that is not one of the shown names — an English column name typed in
    by hand, say — is refused rather than passed through.
    """
    out = []
    for name in shown:
        if name not in real_by_shown:
            raise ValueError("알 수 없는 컬럼입니다")
        out.append(real_by_shown[name])
    return out


def translate_page(page: Mapping[str, Any], real_by_shown: Mapping[str, str]) -> Dict[str, Any]:
    """A table-preview page with Korean column names throughout, and no SQL."""
    shown = {real: name for name, real in real_by_shown.items()}
    rename = lambda name: shown.get(name, name)
    out = {k: v for k, v in page.items() if k != "sql"}
    out["columns"] = [rename(c) for c in page.get("columns", [])]
    out["selected"] = [rename(c) for c in page.get("selected", [])]
    if page.get("order_by") is not None:
        out["order_by"] = rename(page["order_by"])
    out["rows"] = [{rename(k): v for k, v in row.items()} for row in page.get("rows", [])]
    return out


def hide_rule_caveats(rules: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Rule notes such as "컬럼 없음: mccname" name physical columns; say it without the names."""
    return [
        {**r, "caveat": "필요한 컬럼이 없습니다"} if str(r.get("caveat", "")).startswith("컬럼 없음") else dict(r)
        for r in rules
    ]
