# MCP Configuration Examples

Collection of configuration files for different Claude MCP server setups.

## Quick Reference

### Official Claude MCP Server (Recommended)

| Config | Use Case | Args | Env |
|--------|----------|------|-----|
| `claude-desktop.json` | Standard setup | `["mcp", "serve"]` | None |
| `claude-desktop-bypass.json` | Development | `["mcp", "serve", "--permission-mode", "bypassPermissions"]` | None |
| `claude-desktop-readonly.json` | Analysis only | `["mcp", "serve", "--read-only"]` | None |

### Development Environments

| Config | Args | Env |
|--------|------|-----|
| `basic.json` | `["mcp", "serve"]` | None |
| `development.json` | `["mcp", "serve", "--permission-mode", "bypassPermissions", "--debug"]` | None |
| `development-bypass.json` | `["./src/mcp_compliant_server.py", "--permission-mode", "bypassPermissions"]` | `{"DEBUG": "true"}` |

### Production Environments  

| Config | Args | Env |
|--------|------|-----|
| `production.json` | `["mcp", "serve"]` | `{"CLAUDE_MAX_TOKENS": "8000", "CLAUDE_TIMEOUT": "300000"}` |
| `production-secure.json` | `["./src/mcp_compliant_server.py"]` | `{"WORKING_DIR_ONLY": "true", "MAX_TASK_TIMEOUT": "300", "LOG_LEVEL": "INFO"}` |

### Reference Server (For Testing)

| Config | Args | Env |
|--------|------|-----|
| `minimal-server.json` | `["./src/mcp_compliant_server.py"]` | None |
| `mcp-compliant.json` | `["./src/mcp_compliant_server.py"]` | None |
| `mcp-compliant-bypass.json` | `["./src/mcp_compliant_server.py", "--permission-mode", "bypassPermissions"]` | `{"DEBUG": "true", "PROGRESS_NOTIFICATIONS": "true"}` |

## Usage

1. Copy the appropriate config to your Claude Desktop config location:
   - **macOS**: `~/.config/claude-desktop/config.json`
   - **Windows**: `%APPDATA%/Claude/config.json`

2. Restart Claude Desktop

3. The MCP server will be available with the configured tools and permissions

## Recommendation

For most users, start with `claude-desktop.json` for secure operation or `claude-desktop-bypass.json` for development work.