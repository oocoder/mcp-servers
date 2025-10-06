"""FastAPI server for email validation."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from email_validator import is_valid_syntax, get_mx_record, verify_mailbox

app = FastAPI(
    title="Email Validation API",
    description="API for validating email addresses with syntax, DNS, and SMTP verification",
    version="1.0.0"
)


class EmailValidationRequest(BaseModel):
    """Request model for email validation."""
    email: str = Field(..., description="Email address to validate")
    verify_smtp: bool = Field(
        default=False,
        description="Whether to perform SMTP mailbox verification (slower)"
    )


class EmailValidationResponse(BaseModel):
    """Response model for email validation."""
    email: str
    is_valid_syntax: bool
    has_mx_record: bool
    mx_server: Optional[str] = None
    mailbox_verified: Optional[bool] = None
    overall_valid: bool


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Email Validation API",
        "version": "1.0.0",
        "endpoints": {
            "/validate": "POST - Validate an email address",
            "/docs": "GET - API documentation",
        }
    }


@app.post("/validate", response_model=EmailValidationResponse)
async def validate_email(request: EmailValidationRequest):
    """
    Validate an email address.

    Performs the following checks:
    1. Syntax validation using regex
    2. DNS MX record lookup
    3. Optional SMTP mailbox verification

    Args:
        request: Email validation request with email and optional SMTP verification flag

    Returns:
        Validation results including syntax, MX record, and optional mailbox verification

    Raises:
        HTTPException: If validation process encounters an error
    """
    email = request.email.strip()

    if not email:
        raise HTTPException(status_code=400, detail="Email address is required")

    # Step 1: Syntax validation
    syntax_valid = is_valid_syntax(email)

    # Initialize response
    response = {
        "email": email,
        "is_valid_syntax": syntax_valid,
        "has_mx_record": False,
        "mx_server": None,
        "mailbox_verified": None,
        "overall_valid": False
    }

    # If syntax is invalid, return early
    if not syntax_valid:
        return response

    # Step 2: Extract domain and check MX record
    try:
        domain = email.split('@')[1]
        mx_server = get_mx_record(domain)

        response["has_mx_record"] = mx_server is not None
        response["mx_server"] = mx_server

        # If no MX record, email is invalid
        if not mx_server:
            return response

        # Step 3: Optional SMTP mailbox verification
        if request.verify_smtp:
            mailbox_result = verify_mailbox(email, mx_server)
            response["mailbox_verified"] = mailbox_result

            # Overall valid if syntax is valid, has MX record, and mailbox exists
            # If mailbox_verified is None (inconclusive), consider valid if other checks pass
            response["overall_valid"] = (
                syntax_valid and
                mx_server is not None and
                (mailbox_result is True or mailbox_result is None)
            )
        else:
            # Without SMTP verification, valid if syntax and MX record are good
            response["overall_valid"] = syntax_valid and mx_server is not None

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during validation: {str(e)}"
        )

    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
