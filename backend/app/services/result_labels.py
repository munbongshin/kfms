"""Turns what a non-administrator would see into Korean names.

Built once per request from the connection's cached schema, the administrator's
column names and the computed-column terms.
"""
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from app.db.column_labels import apply_labels, merge_expression_terms
from app.db.column_privacy import relabel_rows, result_labels, visible_schema
from app.db.repositories.column_labels import ColumnLabelRepository


class ResultLabeler:
    def __init__(self, labeled_schema: Mapping[str, Sequence[Mapping[str, Any]]], terms: Mapping[str, str]):
        self.schema = labeled_schema
        self.terms = dict(terms)

    @classmethod
    async def load(cls, pool: Any, db: Any, database_id: str) -> "ResultLabeler":
        repo = ColumnLabelRepository(db)
        schema = await pool.get_schema(str(database_id))
        overrides = await repo.overrides(int(database_id))
        terms = {t["func"]: t["label"] for t in merge_expression_terms(await repo.terms())}
        return cls(apply_labels(schema, overrides), terms)

    def visible(self) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, str]]]:
        """The schema as shown, and the way back to the real column names."""
        return visible_schema(self.schema)

    def relabel(self, rows: Sequence[Mapping[str, Any]], sql: str) -> List[Dict[str, Any]]:
        """Query-result rows with Korean column names."""
        return relabel_rows(rows, sql, result_labels(self.schema, sql), self.terms)

    def labels_of(self, table_key: str) -> Dict[str, str]:
        """Column name -> Korean label for one table or view."""
        if table_key not in self.schema:
            return {}
        return result_labels({table_key: self.schema[table_key]}, "")
