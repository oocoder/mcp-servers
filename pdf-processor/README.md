# PDF Processor MCP Server

Professional MCP server that converts PDFs to markdown using intelligent academic paper detection and dual processing engines optimized for Claude Code analysis.

## Features

- **Intelligent Processing**: Auto-detects academic papers for optimal conversion
- **Dual Engines**: marker-pdf for academic content, PyMuPDF for general documents  
- **Smart Caching**: Hash-based caching prevents redundant processing
- **Robust Downloads**: Browser headers, redirect handling, content validation
- **Batch Processing**: Convert multiple PDFs in single operations

## Installation

### Quick Setup (Recommended)

```bash
# 1. Navigate to the project directory
cd pdf-processor

# 2. Create a virtual environment
python3 -m venv venv

# 3. Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 4. Install dependencies
pip install -r mcp_requirements.txt

# 5. Verify setup
python3 verify_setup.py
```

The MCP config is already set up to use the virtual environment. After installation, you can use:

```bash
claude code --mcp-config /path/to/pdf-processor/mcp-config.json
```

### Manual Installation

If you prefer not to use a virtual environment:

```bash
pip install --user -r mcp_requirements.txt
```

Then update `mcp-config.json` line 4 to use your system Python:
```json
"command": "python3",
```

## Verification

Run the verification script to check your setup:

```bash
python3 verify_setup.py
```

This will check:
- ✓ Python version compatibility
- ✓ All required dependencies
- ✓ MCP configuration validity
- ✓ Server script functionality
- ✓ MCP protocol communication

## Configuration

The included `mcp-config.json` is pre-configured and ready to use. It points to the virtual environment Python by default.

### Custom Configuration

To add to your own Claude MCP config:

```json
{
  "mcpServers": {
    "pdf-processor": {
      "command": "/absolute/path/to/pdf-processor/venv/bin/python3",
      "args": ["/absolute/path/to/pdf-processor/src/mcp_pdf_server.py"],
      "cwd": "/absolute/path/to/pdf-processor",
      "env": {
        "PYTHONPATH": "/absolute/path/to/pdf-processor/src",
        "PYTHONUNBUFFERED": "1",
        "PYTHONWARNINGS": "ignore::DeprecationWarning"
      }
    }
  }
}
```

## Available Tools

| Tool | Purpose | Parameters |
|------|---------|------------|
| `convert_pdf_url` | Auto-enhanced conversion | `url`, `include_metadata` |
| `convert_pdf_url_enhanced` | Force marker-pdf processing | `url`, `fallback_to_pymupdf` |
| `convert_pdf_url_with_method` | Manual method selection | `url`, `method` |
| `crawl_pdf_links` | Extract PDF links from pages | `url`, `max_depth` |
| `batch_convert_pdfs` | Process multiple PDFs | `urls`, `include_metadata` |

## Processing Engines

| Engine | Best For | Speed | Quality |
|--------|----------|-------|---------|
| **marker-pdf** | Academic papers | 10-90s | Superior |
| **PyMuPDF** | General documents | ~0.2s | Standard |
| **Auto** | Mixed content | Variable | Optimal |

## Development

```bash
# Run tests
pytest

# Check warning management
python scripts/warning_management.py
```

**Requirements**: Python 3.8+

## Project Structure

```
src/mcp_pdf_server.py    # Main server
mcp-config.json          # Ready-to-use MCP config
tests/                   # Test suite  
scripts/                 # Utilities
cache/                   # PDF cache
mcp_requirements.txt     # Dependencies
```