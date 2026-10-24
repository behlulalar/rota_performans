from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter(prefix="/api", tags=["saglik"])


@router.get("/saglik")
async def saglik(session: AsyncSession = Depends(get_session)):
    """Dağıtım sonrası duman testi ve izleme için: uygulama ve veritabanı ayakta mı."""
    await session.execute(text("SELECT 1"))
    return {"durum": "ok"}
