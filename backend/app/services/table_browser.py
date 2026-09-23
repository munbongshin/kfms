"""Paged, column-selectable reads of one table.

Table and column names cannot be bound as parameters, so every identifier is
checked against the connection's real schema before it reaches the SQL. The
caller supplies that schema; nothing here trusts a name from a request.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

MAX_PAGE_SIZE = 500


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _columns_of(schema: Dict[str, Sequence[str]], table: str) -> List[str]:
    """The table's real columns, or a refusal. The schema is the only authority."""
    if table not in schema:
        raise ValueError(f"unknown table: {table}")
    columns = list(schema[table])
    if not columns:
        raise ValueError(f"table has no columns: {table}")
    return columns


def build_count_query(schema: Dict[str, Sequence[str]], table: str) -> str:
    _columns_of(schema, table)
    return f"SELECT COUNT(*) AS total FROM {quote(table)}"


def build_rows_query(
    schema: Dict[str, Sequence[str]],
    table: str,
    selected: Sequence[str],
    order_by: Optional[str],
    descending: bool,
    limit: int,
    offset: int,
) -> Tuple[str, Dict[str, Any]]:
    """One page of a table.

    `schema` maps every readable table to its real columns, in table order.
    `selected` is what the caller asked for; an empty selection means every
    column. The result keeps the table's own column order either way, so
    ticking boxes in a different sequence cannot reorder the output.
    """
    columns = _columns_of(schema, table)
    known = set(columns)

    unknown = [c for c in selected if c not in known]
    if unknown:
        raise ValueError(f"unknown column(s): {', '.join(unknown)}")

    chosen = [c for c in columns if c in set(selected)] if selected else list(columns)

    if order_by is None:
        order_by = columns[0]
    elif order_by not in known:
        raise ValueError(f"unknown order column: {order_by}")

    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}, got {limit}")

    if offset < 0:
        raise ValueError(f"offset must not be negative, got {offset}")

    # Listing all 157 of card_data's columns makes the SQL unreadable for no
    # gain; a star means the same thing when nothing was filtered out.
    projection = "*" if len(chosen) == len(columns) else ", ".join(quote(c) for c in chosen)
    direction = "DESC" if descending else "ASC"

    # ORDER BY is not optional: PostgreSQL makes no promise about row order
    # without it, so an unordered LIMIT/OFFSET can repeat rows across pages.
    # One column is rarely enough either — card_data's first column repeats
    # across hundreds of rows, and equal sort keys are just as free to move
    # between pages. Every remaining column follows as a tiebreaker, which
    # makes the sort total: rows still tied are identical, so which one a page
    # shows does not matter. Views have no ctid to lean on, so this is the one
    # approach that holds for both tables and views.
    tiebreakers = [quote(c) for c in columns if c != order_by]
    ordering = ", ".join([f"{quote(order_by)} {direction}"] + tiebreakers)

    sql = (
        f"SELECT {projection} FROM {quote(table)}"
        f" ORDER BY {ordering}"
        f" LIMIT :limit OFFSET :offset"
    )
    return sql, {"limit": limit, "offset": offset}


class TableBrowser:
    def __init__(self, pool):
        self.pool = pool

    async def _schema(self, database_id: str) -> Dict[str, List[str]]:
        raw = await self.pool.get_schema(database_id)
        return {table: [c["name"] for c in cols] for table, cols in raw.items()}

    async def read_page(
        self,
        database_id: str,
        table: str,
        selected: Sequence[str],
        order_by: Optional[str],
        descending: bool,
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        schema = await self._schema(database_id)
        sql, params = build_rows_query(
            schema, table, selected, order_by, descending, limit, offset
        )
        columns = list(schema[table])

        total_rows = await self.pool.execute_query(
            database_id, build_count_query(schema, table)
        )
        rows = await self.pool.execute_query(database_id, sql, params)

        return {
            "table": table,
            # The query is ours, not the caller's — showing it lets a reviewer
            # see exactly what produced the page and copy it into the query screen.
            "sql": sql,
            "columns": columns,
            "selected": [c for c in columns if c in set(selected)] if selected else columns,
            "order_by": order_by or columns[0],
            "descending": descending,
            "total": int(total_rows[0]["total"]) if total_rows else 0,
            "offset": offset,
            "limit": limit,
            "rows": rows,
        }
