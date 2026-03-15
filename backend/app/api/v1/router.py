from fastapi import APIRouter
from app.api.v1 import health, auth, ingestion, cost, anomaly as anomaly_router_module
from app.api.v1 import recommendation as recommendation_router_module
from app.api.v1 import attribution as attribution_router_module
from app.api.v1 import settings as settings_router_module
from app.api.v1 import budget as budget_router_module
from app.api.v1 import notification as notification_router_module

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ingestion.router)
api_router.include_router(cost.router)
api_router.include_router(anomaly_router_module.router, prefix="/anomalies", tags=["anomalies"])
api_router.include_router(
    recommendation_router_module.router,
    prefix="/recommendations",
    tags=["recommendations"],
)
api_router.include_router(
    attribution_router_module.router,
    prefix="/attribution",
    tags=["attribution"],
)
api_router.include_router(
    settings_router_module.router,
    prefix="/settings",
    tags=["settings"],
)
api_router.include_router(
    budget_router_module.router,
    prefix="/budgets",
    tags=["budgets"],
)
api_router.include_router(
    notification_router_module.router,
    prefix="/notifications",
    tags=["notifications"],
)
