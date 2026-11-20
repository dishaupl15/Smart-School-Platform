from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.application import create_app
from app.db.session import get_db


def test_api_initialization_registers_versioned_routes() -> None:
    application = create_app()
    paths = set(application.openapi()["paths"])

    assert "/api/v1/health" in paths
    assert "/api/v1/health/database" in paths


def test_health_endpoint_returns_application_status(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "smart-school-api"}


def test_database_health_endpoint_returns_ok_when_query_succeeds() -> None:
    application = create_app()
    session = MagicMock()
    application.dependency_overrides[get_db] = lambda: session

    with TestClient(application) as client:
        response = client.get("/api/v1/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "database"}
    session.execute.assert_called_once()


def test_database_health_endpoint_hides_connection_error_details() -> None:
    application = create_app()
    session = MagicMock()
    session.execute.side_effect = OperationalError(
        "SELECT 1",
        {},
        Exception("private connection details"),
    )
    application.dependency_overrides[get_db] = lambda: session

    with TestClient(application) as client:
        response = client.get("/api/v1/health/database")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "service": "database"}
    assert "private connection details" not in response.text
