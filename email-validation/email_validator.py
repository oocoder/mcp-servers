"""Email validation module with syntax, DNS, and SMTP verification."""

import re
import smtplib
import socket
from typing import Optional
import dns.resolver
import dns.exception


def is_valid_syntax(email: str) -> bool:
    """
    Validate email syntax using regex pattern.

    Args:
        email: Email address to validate

    Returns:
        True if email syntax is valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False

    # RFC 5322 compliant email regex pattern (simplified)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    return bool(re.match(pattern, email))


def get_mx_record(domain: str) -> Optional[str]:
    """
    Perform DNS lookup to get MX record for domain.

    Args:
        domain: Domain name to lookup

    Returns:
        Primary MX server hostname if found, None otherwise
    """
    if not domain or not isinstance(domain, str):
        return None

    try:
        # Query MX records for the domain
        mx_records = dns.resolver.resolve(domain, 'MX')

        # Sort by priority (lower value = higher priority)
        mx_records = sorted(mx_records, key=lambda r: r.preference)

        if mx_records:
            # Return the hostname of the highest priority MX server
            return str(mx_records[0].exchange).rstrip('.')

        return None

    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers,
            dns.exception.Timeout, Exception):
        # Domain doesn't exist, no MX records, or DNS error
        return None


def verify_mailbox(email: str, mx_server: str, timeout: int = 10) -> Optional[bool]:
    """
    Verify if mailbox exists using SMTP without sending email.

    Args:
        email: Email address to verify
        mx_server: MX server hostname to connect to
        timeout: Connection timeout in seconds

    Returns:
        True if mailbox exists, False if doesn't exist, None if verification failed
    """
    if not email or not mx_server:
        return None

    try:
        # Set socket timeout
        socket.setdefaulttimeout(timeout)

        # Connect to the mail server
        server = smtplib.SMTP(timeout=timeout)
        server.connect(mx_server)

        # Identify ourselves
        server.helo()

        # Provide a sender address (required for RCPT TO)
        server.mail('verify@example.com')

        # Check if recipient exists
        code, message = server.rcpt(email)

        # Close connection
        server.quit()

        # 250 = success, mailbox exists
        # 550 = mailbox doesn't exist
        # Other codes are inconclusive
        if code == 250:
            return True
        elif code == 550:
            return False
        else:
            return None

    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
            socket.timeout, socket.gaierror, OSError, Exception):
        # Connection failed or other error - inconclusive
        return None
    finally:
        try:
            server.quit()
        except:
            pass
