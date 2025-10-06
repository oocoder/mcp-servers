"""Tests for email validation functionality."""

import pytest
from email_validator import is_valid_syntax, get_mx_record, verify_mailbox


class TestSyntaxValidation:
    """Test email syntax validation."""

    def test_valid_email_basic(self):
        """Test basic valid email format."""
        assert is_valid_syntax("test@example.com") is True

    def test_valid_email_with_subdomain(self):
        """Test valid email with subdomain."""
        assert is_valid_syntax("user@mail.example.com") is True

    def test_valid_email_with_plus(self):
        """Test valid email with plus sign."""
        assert is_valid_syntax("user+tag@example.com") is True

    def test_valid_email_with_numbers(self):
        """Test valid email with numbers."""
        assert is_valid_syntax("user123@example123.com") is True

    def test_invalid_email_no_at(self):
        """Test invalid email without @ symbol."""
        assert is_valid_syntax("userexample.com") is False

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        assert is_valid_syntax("user@") is False

    def test_invalid_email_no_local(self):
        """Test invalid email without local part."""
        assert is_valid_syntax("@example.com") is False

    def test_invalid_email_double_at(self):
        """Test invalid email with double @ symbol."""
        assert is_valid_syntax("user@@example.com") is False

    def test_invalid_email_spaces(self):
        """Test invalid email with spaces."""
        assert is_valid_syntax("user @example.com") is False

    def test_empty_string(self):
        """Test empty string."""
        assert is_valid_syntax("") is False


class TestMXRecordValidation:
    """Test MX record lookup."""

    def test_valid_domain_with_mx(self):
        """Test domain with valid MX records."""
        mx_record = get_mx_record("gmail.com")
        assert mx_record is not None
        assert len(mx_record) > 0

    def test_invalid_domain_no_mx(self):
        """Test invalid domain without MX records."""
        mx_record = get_mx_record("this-domain-definitely-does-not-exist-12345.com")
        assert mx_record is None

    def test_empty_domain(self):
        """Test empty domain."""
        mx_record = get_mx_record("")
        assert mx_record is None


class TestMailboxVerification:
    """Test SMTP mailbox verification."""

    def test_verify_mailbox_timeout(self):
        """Test mailbox verification with timeout handling."""
        # This should handle timeout gracefully
        result = verify_mailbox("test@example.com", "nonexistent-server.example.com")
        assert result in [True, False, None]  # Accept any result, just shouldn't crash

    def test_verify_mailbox_invalid_server(self):
        """Test mailbox verification with invalid server."""
        result = verify_mailbox("test@example.com", "")
        assert result is False or result is None
