# PDF Processor MCP Server

Professional MCP server that converts PDFs to markdown using intelligent academic paper detection and dual processing engines optimized for Claude Code analysis.

## Features

- **Intelligent Processing**: Auto-detects academic papers for optimal conversion
- **Dual Engines**: marker-pdf for academic content, PyMuPDF for general documents  
- **Smart Caching**: Hash-based caching prevents redundant processing
- **Robust Downloads**: Browser headers, redirect handling, content validation
- **Batch Processing**: Convert multiple PDFs in single operations

## Installation

```bash
pip install -r mcp_requirements.txt
```

## Configuration

### Option 1: Use included config
```bash
claude code --mcp-config /path/to/pdf-processor/mcp-config.json
```

### Option 2: Add to your Claude MCP config
```json
{
  "mcpServers": {
    "pdf-processor": {
      "command": "python3",
      "args": ["/path/to/pdf-processor/src/mcp_pdf_server.py"],
      "cwd": "/path/to/pdf-processor",
      "env": {
        "PYTHONPATH": "/path/to/pdf-processor/src",
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