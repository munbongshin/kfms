"""
Business glossary API.
Terms and definitions the LLM is given when a question uses them.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.db.repositories.glossary import GlossaryRepository

router = APIRouter(prefix="/glossary", tags=["Glossary"])


class TermIn(BaseModel):
    term: str = Field(..., min_length=1, max_length=100)
    definition: str = Field(..., min_length=1, max_length=1000)


class TermOut(BaseModel):
    id: int
    term: str
    definition: str


def _out(row) -> TermOut:
    return TermOut(id=row.id, term=row.term, definition=row.definition)


@router.get("", response_model=List[TermOut])
async def list_terms(db: AsyncSession = Depends(get_db)):
    return [_out(r) for r in await GlossaryRepository(db).list_all()]


@router.post("", response_model=TermOut, status_code=status.HTTP_201_CREATED)
async def create_term(body: TermIn, db: AsyncSession = Depends(get_db)):
    repo = GlossaryRepository(db)
    term = body.term.strip()
    if await repo.get_by_term(term):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"'{term}' 용어가 이미 있습니다")
    return _out(await repo.create(term, body.definition.strip()))


@router.put("/{term_id}", response_model=TermOut)
async def update_term(term_id: int, body: TermIn, db: AsyncSession = Depends(get_db)):
    repo = GlossaryRepository(db)
    term = body.term.strip()
    other = await repo.get_by_term(term)
    if other and other.id != term_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"'{term}' 용어가 이미 있습니다")
    row = await repo.update(term_id, term, body.definition.strip())
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="용어를 찾을 수 없습니다")
    return _out(row)


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_term(term_id: int, db: AsyncSession = Depends(get_db)):
    if not await GlossaryRepository(db).delete(term_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="용어를 찾을 수 없습니다")
