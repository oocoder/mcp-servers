# Claude MCP Server v1.4.0

Production-ready Model Context Protocol (MCP) server with comprehensive development tools and optimized Task tool implementation.

## Quick Start

```bash
claude mcp serve
```

## Features

- **14 Development Tools**: Complete toolkit for software development workflows
- **Task Tool**: Multi-step workflow execution with progress tracking
- **MCP Compliant**: Native protocol support with permissions and capability negotiation
- **Fast Unit Tests**: Comprehensive test suite with <1s execution time
- **Production Ready**: Robust error handling and validation

## Installation

```bash
npm install -g @anthropic-ai/claude-cli
# Set ANTHROPIC_API_KEY in environment
```

## Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "claude": {
      "command": "claude",
      "args": ["mcp", "serve"]
    }
  }
}
```

## Available Tools

- **Task**: Multi-step workflow execution
- **Read/Write/Edit**: File operations and batch editing
- **Bash**: Shell command execution
- **Glob/Grep**: File and content search
- **TodoWrite**: Task management
- **WebFetch/WebSearch**: Web content access
- **NotebookEdit**: Jupyter notebook support

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All tests are fast unit tests with comprehensive mocking and no external dependencies.

## Project Structure

```
claude/
├── src/server.py          # Main MCP server
├── tests/                 # Unit test suite  
├── config-samples/        # Configuration examples
└── examples/              # Demo workflows
```

## License

MIT License