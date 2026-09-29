import pytest
from unittest.mock import patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from saas_core.db.session import get_db
from saas_core.auth.dependencies import get_current_user
from saas_core.auth.firebase import verify_firebase_id_token
from saas_core.exceptions import AuthenticationError
from saas_core.api.schemas import UserResponse
from saas_core.db.models import User

app = FastAPI()


@app.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user


def test_auth_missing_header(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/me")
    assert response.status_code == 401
    assert "Authorization header missing" in response.json()["detail"]


def test_auth_invalid_header_format(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/me", headers={"Authorization": "Basic 12345"})
    assert response.status_code == 401
    assert "Invalid Authorization header format" in response.json()["detail"]


def test_auth_invalid_token(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    with patch("saas_core.auth.dependencies.verify_firebase_id_token") as mock_verify:
        mock_verify.side_effect = AuthenticationError("Invalid authentication token")
        response = client.get("/me", headers={"Authorization": "Bearer badtoken"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authentication token"


def test_auth_successful_sync(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    with patch("saas_core.auth.dependencies.verify_firebase_id_token") as mock_verify:
        mock_verify.return_value = {
            "uid": "fb_user_abc",
            "email": "user@test.com",
            "name": "Alex Test"
        }
        response = client.get("/me", headers={"Authorization": "Bearer goodtoken"})
        assert response.status_code == 200
        data = response.json()
        assert data["firebase_uid"] == "fb_user_abc"
        assert data["email"] == "user@test.com"
        assert data["display_name"] == "Alex Test"
        assert data["status"] == "active"
        assert data["trial_used"] is False

    # Second request should retrieve same user and update if needed
    with patch("saas_core.auth.dependencies.verify_firebase_id_token") as mock_verify:
        mock_verify.return_value = {
            "uid": "fb_user_abc",
            "email": "user_updated@test.com",
            "name": "Alex Updated"
        }
        response = client.get("/me", headers={"Authorization": "Bearer goodtoken"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user_updated@test.com"
        assert data["display_name"] == "Alex Updated"
