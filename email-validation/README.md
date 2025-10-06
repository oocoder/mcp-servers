# Email Validation API

A FastAPI-based email validation service that performs comprehensive email address validation using syntax checking, DNS MX record lookup, and optional SMTP mailbox verification.

## Features

- **Syntax Validation**: RFC 5322 compliant email format validation
- **DNS MX Record Lookup**: Verifies domain has valid mail server configuration
- **SMTP Mailbox Verification**: Optional real-time mailbox existence check (without sending email)
- **RESTful API**: Simple HTTP API with JSON responses
- **Comprehensive Testing**: 24+ tests covering all validation scenarios

## Installation

1. Clone the repository and navigate to the project directory:
```bash
cd email-validation
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Server

Run the server using uvicorn:
```bash
python main.py
```

Or directly with uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

### API Endpoints

#### POST /validate

Validates an email address with multiple verification levels.

**Request:**
```json
{
  "email": "user@example.com",
  "verify_smtp": false
}
```

**Parameters:**
- `email` (required): Email address to validate
- `verify_smtp` (optional, default: false): Enable SMTP mailbox verification

**Response:**
```json
{
  "email": "user@example.com",
  "is_valid_syntax": true,
  "has_mx_record": true,
  "mx_server": "mail.example.com",
  "mailbox_verified": null,
  "overall_valid": true
}
```

**Response Fields:**
- `email`: The validated email address
- `is_valid_syntax`: Whether email syntax is valid
- `has_mx_record`: Whether domain has MX records
- `mx_server`: Primary MX server hostname (if found)
- `mailbox_verified`: SMTP verification result (true/false/null if not performed or inconclusive)
- `overall_valid`: Overall validation result

#### GET /

Returns API information and available endpoints.

#### GET /health

Health check endpoint.

### Example Usage

**cURL:**
```bash
# Basic validation (syntax + MX record)
curl -X POST "http://localhost:8000/validate" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com"}'

# With SMTP verification
curl -X POST "http://localhost:8000/validate" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com", "verify_smtp": true}'
```

**Python:**
```python
import requests

response = requests.post(
    "http://localhost:8000/validate",
    json={"email": "test@gmail.com", "verify_smtp": False}
)
print(response.json())
```

## Testing

Run the test suite:
```bash
pytest -v
```

Run specific test files:
```bash
pytest test_email_validator.py -v
pytest test_api.py -v
```

## Type Checking

Run pyright type checking:
```bash
pyright -p pyright_cli.json *.py
```

## Architecture

The project consists of three main components:

1. **email_validator.py**: Core validation logic
   - `is_valid_syntax()`: Regex-based syntax validation
   - `get_mx_record()`: DNS MX record lookup
   - `verify_mailbox()`: SMTP mailbox verification

2. **main.py**: FastAPI application
   - REST API endpoints
   - Request/response models
   - Error handling

3. **Tests**: Comprehensive test coverage
   - Unit tests for validation functions
   - Integration tests for API endpoints

## Limitations & Considerations

- **SMTP Verification**: Some mail servers may reject verification attempts or use greylisting. Results may be inconclusive (null).
- **Rate Limiting**: Excessive SMTP verification requests may trigger rate limiting or blacklisting.
- **Timeout Handling**: Network timeouts are handled gracefully (default 10s timeout).
- **Catch-all Domains**: Domains with catch-all configurations will always return true for SMTP verification.

## Dependencies

- **FastAPI**: Modern web framework for building APIs
- **dnspython**: DNS toolkit for MX record lookups
- **Pydantic**: Data validation using Python type hints
- **Uvicorn**: ASGI server for running FastAPI applications
- **pytest**: Testing framework

## License

This project is provided as-is for educational and development purposes.

## Status

**Version**: 1.0.0
**Status**: MVP Complete
**Tests**: 24/24 passing
**Type Errors**: 0
