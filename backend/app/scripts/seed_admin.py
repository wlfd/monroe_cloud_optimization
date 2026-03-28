"""
Admin seed script. Run once after alembic upgrade head:
  docker compose exec api python -m app.scripts.seed_admin

Reads FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD from environment / .env.
Does nothing if an admin user already exists.
"""

import asyncio
import sys

from pwdlib import PasswordHash
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User

password_hash = PasswordHash.recommended()


async def seed():
    if not settings.FIRST_ADMIN_EMAIL or not settings.FIRST_ADMIN_PASSWORD:
        print("ERROR: FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD must be set in environment.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.role == "admin").limit(1))
        if existing.scalar_one_or_none():
            print("Admin user already exists. Nothing to do.")
            return

        admin = User(
            email=settings.FIRST_ADMIN_EMAIL,
            password_hash=password_hash.hash(settings.FIRST_ADMIN_PASSWORD),
            full_name="Admin",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print(f"Admin user created: {settings.FIRST_ADMIN_EMAIL}")


if __name__ == "__main__":
    asyncio.run(seed())
