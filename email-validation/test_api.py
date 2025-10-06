"""Tests for FastAPI email validation server."""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root(self):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check(self):
        """Test health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestValidateEndpoint:
    """Test email validation endpoint."""

    def test_validate_valid_email_syntax_only(self):
        """Test validation with valid email syntax."""
        response = client.post(
            "/validate",
            json={"email": "test@gmail.com", "verify_smtp": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@gmail.com"
        assert data["is_valid_syntax"] is True
        assert data["has_mx_record"] is True
        assert data["mx_server"] is not None
        assert data["mailbox_verified"] is None
        assert data["overall_valid"] is True

    def test_validate_invalid_syntax(self):
        """Test validation with invalid email syntax."""
        response = client.post(
            "/validate",
            json={"email": "invalid-email", "verify_smtp": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "invalid-email"
        assert data["is_valid_syntax"] is False
        assert data["has_mx_record"] is False
        assert data["overall_valid"] is False

    def test_validate_invalid_domain(self):
        """Test validation with non-existent domain."""
        response = client.post(
            "/validate",
            json={"email": "test@nonexistentdomain12345.com", "verify_smtp": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid_syntax"] is True
        assert data["has_mx_record"] is False
        assert data["overall_valid"] is False

    def test_validate_empty_email(self):
        """Test validation with empty email."""
        response = client.post(
            "/validate",
            json={"email": "", "verify_smtp": False}
        )
        assert response.status_code == 400
        assert "Email address is required" in response.json()["detail"]

    def test_validate_with_whitespace(self):
        """Test validation trims whitespace."""
        response = client.post(
            "/validate",
            json={"email": "  test@gmail.com  ", "verify_smtp": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@gmail.com"
        assert data["is_valid_syntax"] is True

    def test_validate_missing_email_field(self):
        """Test validation without email field."""
        response = client.post(
            "/validate",
            json={"verify_smtp": False}
        )
        assert response.status_code == 422  # Validation error

    def test_validate_default_verify_smtp_false(self):
        """Test that verify_smtp defaults to False."""
        response = client.post(
            "/validate",
            json={"email": "test@gmail.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mailbox_verified"] is None  # Should not be verified by default
