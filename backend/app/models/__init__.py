# Import all models here so Alembic autogenerate detects them
from app.models.user import User, UserSession  # noqa: F401
from app.models import billing  # noqa: F401
from app.models import recommendation  # noqa: F401
from app.models import attribution  # noqa: F401
from app.models import notification  # noqa: F401
from app.models import budget  # noqa: F401
