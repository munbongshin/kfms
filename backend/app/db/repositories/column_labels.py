"""Repository for column display names and computed-column terms."""
from typing import Dict, Iterable, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.column_labels import Override
from app.db.models import ColumnLabel, ExpressionTerm


class ColumnLabelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def overrides(self, connection_id: int) -> List[Override]:
        result = await self.session.execute(
            select(ColumnLabel)
            .where(ColumnLabel.connection_id == connection_id)
            .order_by(ColumnLabel.column_name, ColumnLabel.table_key)
        )
        return [Override(r.table_key, r.column_name, r.label, r.id) for r in result.scalars().all()]

    async def _find(self, connection_id: int, table_key: Optional[str], column_name: str) -> Optional[ColumnLabel]:
        where = [ColumnLabel.connection_id == connection_id, ColumnLabel.column_name == column_name]
        where.append(ColumnLabel.table_key.is_(None) if table_key is None else ColumnLabel.table_key == table_key)
        result = await self.session.execute(select(ColumnLabel).where(*where))
        return result.scalar_one_or_none()

    async def _put(self, connection_id: int, table_key: Optional[str], column_name: str, label: str) -> None:
        row = await self._find(connection_id, table_key, column_name)
        if row is None:
            self.session.add(ColumnLabel(
                connection_id=connection_id, table_key=table_key, column_name=column_name, label=label
            ))
        else:
            row.label = label

    async def set(self, connection_id: int, table_key: Optional[str], column_name: str, label: str) -> None:
        await self._put(connection_id, table_key, column_name, label)
        await self.session.commit()

    async def set_many(self, connection_id: int, items: Iterable[Override]) -> int:
        """All or nothing: a sheet is applied as a whole."""
        count = 0
        for item in items:
            await self._put(connection_id, item.table_key, item.column_name, item.label)
            count += 1
        await self.session.commit()
        return count

    async def clear(self, connection_id: int, table_key: Optional[str], column_name: str) -> bool:
        row = await self._find(connection_id, table_key, column_name)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.commit()
        return True

    async def delete(self, connection_id: int, label_id: int) -> bool:
        result = await self.session.execute(
            delete(ColumnLabel).where(ColumnLabel.id == label_id, ColumnLabel.connection_id == connection_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    # --- computed-column terms ------------------------------------------------------------
    async def terms(self) -> Dict[str, str]:
        result = await self.session.execute(select(ExpressionTerm))
        return {r.function: r.label for r in result.scalars().all()}

    async def set_term(self, func: str, label: str) -> None:
        row = await self.session.get(ExpressionTerm, func)
        if row is None:
            self.session.add(ExpressionTerm(function=func, label=label))
        else:
            row.label = label
        await self.session.commit()

    async def reset_term(self, func: str) -> None:
        await self.session.execute(delete(ExpressionTerm).where(ExpressionTerm.function == func))
        await self.session.commit()
