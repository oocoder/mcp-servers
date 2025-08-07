# MCP Configuration Examples

Collection of configuration files for different Claude MCP server setups.

## Quick Reference

### Official Claude MCP Server (Recommended)

| Config | Use Case | Permission Mode |
|--------|----------|----------------|
| `claude-desktop.json` | Standard setup | Default (secure) |
| `claude-desktop-bypass.json` | Development | Bypass permissions |
| `claude-desktop-readonly.json` | Analysis only | Read-only |

### Development Environments

| Config | Description |
|--------|-------------|
| `basic.json` | Minimal configuration |
| `development.json` | Development with logging |
| `development-bypass.json` | Development with full permissions |

### Production Environments  

| Config | Description |
|--------|-------------|
| `production.json` | Production ready |
| `production-secure.json` | Production with security limits |

### Reference Server (For Testing)

| Config | Description |
|--------|-------------|
| `minimal-server.json` | Reference implementation |
| `mcp-compliant.json` | MCP-compliant server |
| `mcp-compliant-bypass.json` | MCP server with bypass mode |

## Usage

1. Copy the appropriate config to your Claude Desktop config location:
   - **macOS**: `~/.config/claude-desktop/config.json`
   - **Windows**: `%APPDATA%/Claude/config.json`

2. Restart Claude Desktop

3. The MCP server will be available with the configured tools and permissions

## Recommendation

For most users, start with `claude-desktop.json` for secure operation or `claude-desktop-bypass.json` for development work.