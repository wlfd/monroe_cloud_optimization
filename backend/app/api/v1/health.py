from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready", "database": "ok"}
