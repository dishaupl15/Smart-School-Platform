from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse
from app.services.health_service import database_is_healthy

router = APIRouter()


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="smart-school-api")


@router.get("/database", response_model=HealthResponse)
def database_health_check(session: Session = Depends(get_db)) -> HealthResponse | JSONResponse:
    if not database_is_healthy(session):
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "service": "database"},
        )
    return HealthResponse(status="ok", service="database")
