# Claude MCP Server

Professional Model Context Protocol (MCP) server providing complete development capabilities through Claude's built-in MCP server and comprehensive testing framework.

## Quick Start

```bash
claude mcp serve
```

## Features

- **Complete Development Environment**: 14 integrated tools for full development lifecycle
- **Native MCP Compliance**: Progress notifications, permissions, capability negotiation
- **Task Execution**: Complex workflows from natural language using the Task tool
- **Comprehensive Testing**: 17 test cases covering MCP compliance and negative scenarios
- **Production Ready**: Configurable security modes and monitoring

## Installation

```bash
npm install -g @anthropic-ai/claude-cli
# Set ANTHROPIC_API_KEY in environment
```

## Configuration Examples

### Basic Setup
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

### Development (Bypass Permissions)
```json
{
  "mcpServers": {
    "claude": {
      "command": "claude", 
      "args": ["mcp", "serve", "--permission-mode", "bypassPermissions"]
    }
  }
}
```

### Production (Secure)
```json
{
  "mcpServers": {
    "claude": {
      "command": "claude",
      "args": ["mcp", "serve"],
      "env": {
        "CLAUDE_MAX_TOKENS": "8000",
        "CLAUDE_TIMEOUT": "300000"
      }
    }
  }
}
```

## Available Tools

**Core Development:**
- **Task**: Execute complex multi-step workflows
- **Read/Write/Edit**: File operations
- **MultiEdit**: Batch file editing
- **Bash**: Shell command execution

**Search & Analysis:**
- **Glob**: Pattern-based file search
- **Grep**: Content search with regex
- **LS**: Directory listing

**Specialized:**
- **TodoWrite**: Task management
- **WebFetch/WebSearch**: Web content access
- **NotebookEdit**: Jupyter notebook editing
- **ExitPlanMode**: Planning workflow management

## Usage

### Execute Complex Workflows
```python
result = await session.call_tool("Task", {
    "prompt": "Build a REST API with authentication, include tests and documentation"
})
```

### File-Based Task Execution
```python
# Read task file
content = await session.call_tool("Read", {"file_path": "./tasks.md"})

# Execute all tasks
result = await session.call_tool("Task", {
    "prompt": f"Execute tasks from file:\n\n{content}"
})
```

## Testing

### Run Test Suite
```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Test Coverage: 100% Pass Rate (17/17 tests)

**✅ MCP Compliance**: Progress notifications, capability declaration, tool schemas  
**✅ Server Integration**: Discovery, initialization, error handling  
**✅ Negative Testing**: Input validation, security checks, boundary conditions  
**✅ Tool Functionality**: Task and TodoWrite tool validation

### Test Categories
- **MCP Protocol Compliance**: 4 tests
- **Server Integration**: 4 tests  
- **Negative/Security Cases**: 5 tests
- **Direct Integration**: 2 tests
- **Progress Flow**: 2 tests

## Project Structure

```
claude/
├── src/
│   └── mcp_compliant_server.py    # Reference MCP server implementation
├── tests/
│   ├── test_mcp_compliance.py     # MCP protocol compliance tests
│   ├── test_minimal_server.py     # Server integration tests
│   ├── test_negative_cases.py     # Security and validation tests
│   └── ...
├── config-samples/                # Configuration examples
├── docs/                          # Documentation
├── examples/                      # Demo scripts
└── README.md
```

## Security & Permissions

### Permission Modes
- **Default**: Balanced permissions (production recommended)
- **`--permission-mode bypassPermissions`**: Development mode
- **`--read-only`**: Read-only operations only

### Security Features
- Input validation and sanitization
- Configurable permission controls
- Safe command execution
- Error handling and recovery

## Integration

### Claude Desktop
Add to `~/.config/claude-desktop/config.json`

### Python Client
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="claude", args=["mcp", "serve"]
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # Use tools...
```

## Reference Implementation

This repository includes a minimal MCP-compliant server (`src/mcp_compliant_server.py`) demonstrating:
- MCP progress notification specification compliance
- Task and TodoWrite tool implementation  
- Best practices for MCP server development
- Comprehensive test coverage

## License

MIT License - See LICENSE file for details

## Support

For issues with the built-in Claude MCP server, consult the official Claude CLI documentation. For questions about this testing framework or reference implementation, please open an issue.