# Import all models here so Alembic autogenerate detects them
from app.models import (
    attribution,  # noqa: F401
    billing,  # noqa: F401
    budget,  # noqa: F401
    notification,  # noqa: F401
    recommendation,  # noqa: F401
)
from app.models.user import User, UserSession  # noqa: F401
