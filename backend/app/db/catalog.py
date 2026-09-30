"""A connection's tables, views and columns, read from PostgreSQL's catalog.

One query covers every schema the connection may read and every relation a
question can be asked about: tables, partitioned tables (not their partitions,
which would repeat the parent's rows), views, materialized views and foreign
tables — with each table's and column's COMMENT. information_schema cannot do
this: it omits materialized views and needs a query per table.

Tables in `public` keep their bare name; others are named `schema.table`, which
is also how the LLM and the table browser refer to them.
"""
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple


CATALOG_SQL = r"""
SELECT
    n.nspname                              AS schema_name,
    c.relname                              AS table_name,
    c.relkind::text                        AS relkind,  -- "char" arrives as bytes otherwise
    obj_description(c.oid, 'pg_class')     AS table_comment,
    a.attname                              AS column_name,
    format_type(a.atttypid, a.atttypmod)   AS data_type,
    NOT a.attnotnull                       AS nullable,
    pg_get_expr(d.adbin, d.adrelid)        AS column_default,
    col_description(c.oid, a.attnum)       AS column_comment
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND NOT c.relispartition
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg\_toast%'
  AND n.nspname NOT LIKE 'pg\_temp%'
  AND has_schema_privilege(n.oid, 'USAGE')
  AND has_table_privilege(c.oid, 'SELECT')
ORDER BY (n.nspname <> 'public'), n.nspname, c.relname, a.attnum
"""

# Which columns of which relation each view (or materialized view) reads.
# PostgreSQL records a dependency per referenced column — including columns
# used only in WHERE — so this says exactly what a set of views can stand in
# for, even when a view renames the columns it selects.
DEPENDENCY_SQL = r"""
SELECT DISTINCT
    sn.nspname  AS source_schema,
    sc.relname  AS source_name,
    dn.nspname  AS view_schema,
    dv.relname  AS view_name,
    a.attname   AS column_name,
    a.attnum    AS column_position
FROM pg_depend d
JOIN pg_rewrite r    ON r.oid = d.objid
JOIN pg_class dv     ON dv.oid = r.ev_class
JOIN pg_namespace dn ON dn.oid = dv.relnamespace
JOIN pg_class sc     ON sc.oid = d.refobjid
JOIN pg_namespace sn ON sn.oid = sc.relnamespace
JOIN pg_attribute a  ON a.attrelid = sc.oid AND a.attnum = d.refobjsubid
WHERE d.classid = 'pg_rewrite'::regclass
  AND d.refclassid = 'pg_class'::regclass
  AND d.refobjsubid > 0
  AND dv.oid <> sc.oid
  AND dv.relkind IN ('v', 'm')
ORDER BY sn.nspname, sc.relname, dn.nspname, dv.relname, a.attnum
"""

KINDS = {
    "r": "table",
    "p": "table",
    "v": "view",
    "m": "materialized_view",
    "f": "foreign_table",
}

Catalog = Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]


def table_key(schema: str, name: str) -> str:
    """How a table is named everywhere: bare in public, else schema.table.

    A public name that itself contains a dot is qualified too, so splitting a
    key at its first dot is never ambiguous.
    """
    if schema == "public" and "." not in name:
        return name
    return f"{schema}.{name}"


def split_key(key: str) -> Tuple[str, str]:
    if "." in key:
        schema, name = key.split(".", 1)
        return schema, name
    return "public", key


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def quote_relation(key: str) -> str:
    """The key as a safe SQL relation reference."""
    schema, name = split_key(key)
    return quote(name) if schema == "public" and key == name else f"{quote(schema)}.{quote(name)}"


def borrow_missing_comments(columns: Dict[str, List[Dict[str, Any]]]) -> None:
    """Give uncommented columns the comment a same-named column has elsewhere.

    PostgreSQL does not copy comments onto view columns, and the card views are
    plain SELECTs over card_data, so their columns would otherwise have no
    label. A column's own comment always wins.
    """
    known: Dict[str, str] = {}
    for cols in columns.values():
        for column in cols:
            comment = (column.get("comment") or "").strip()
            if comment:
                known.setdefault(column["name"], comment)

    for cols in columns.values():
        for column in cols:
            if not (column.get("comment") or "").strip():
                column["comment"] = known.get(column["name"])


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def build_catalog(
    rows: Iterable[Mapping[str, Any]],
    dependencies: Iterable[Mapping[str, Any]] = (),
) -> Catalog:
    """Tables (key -> info) and their columns (key -> column list), in order.

    Each table also lists `derived_views`: the readable views built on it and
    the source columns each one reads. Nothing is decided here — the screen
    uses it to *suggest* leaving out a table its views fully cover.
    """
    tables: Dict[str, Dict[str, Any]] = {}
    columns: Dict[str, List[Dict[str, Any]]] = {}

    for r in rows:
        key = table_key(r["schema_name"], r["table_name"])
        if key not in tables:
            tables[key] = {
                "key": key,
                "schema": r["schema_name"],
                "name": r["table_name"],
                "kind": KINDS.get(_text(r["relkind"]), "table"),
                "comment": (r["table_comment"] or "").strip() or None,
                "derived_views": {},
            }
            columns[key] = []
        columns[key].append({
            "name": r["column_name"],
            "type": r["data_type"],
            "nullable": bool(r["nullable"]),
            "default": r["column_default"],
            # The business name (COMMENT ON COLUMN), e.g. 카드번호.
            "comment": r["column_comment"],
        })

    for d in dependencies:
        source = table_key(d["source_schema"], d["source_name"])
        view = table_key(d["view_schema"], d["view_name"])
        # Only views this connection can read may stand in for a table.
        if source not in tables or view not in tables:
            continue
        read = tables[source]["derived_views"].setdefault(view, [])
        if d["column_name"] not in read:
            read.append(d["column_name"])

    borrow_missing_comments(columns)
    return tables, columns


class SchemaCache:
    """Catalogs per connection, kept for a while so each question does not
    re-read the whole catalog. Dropped when a connection or its tables change."""

    def __init__(self, ttl_seconds: float = 300, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl_seconds
        self.clock = clock
        self._entries: Dict[str, Tuple[float, Any]] = {}

    def get(self, connection_id: str) -> Optional[Any]:
        entry = self._entries.get(connection_id)
        if entry is None or self.clock() - entry[0] > self.ttl:
            return None
        return entry[1]

    def put(self, connection_id: str, value: Any) -> None:
        self._entries[connection_id] = (self.clock(), value)

    def invalidate(self, connection_id: str) -> None:
        self._entries.pop(connection_id, None)
