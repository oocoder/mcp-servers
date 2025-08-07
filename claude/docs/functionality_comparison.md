# MCP Server Functionality Comparison

## Agent Discovery Perspective

### `claude-code` Server
**Discovered as:** Low-level development toolkit
**Capabilities:** Direct file/system operations + AI assistance

| Tool | Agent Sees | Purpose |
|------|------------|---------|
| `Read` | Read any file | Access file contents |
| `Write` | Create/overwrite files | Generate new files |
| `Edit` | Modify existing files | Update specific content |
| `Bash` | Execute shell commands | Run build scripts, tests, etc. |
| `Glob` | Find files by pattern | Locate files to work with |
| `Grep` | Search file contents | Find specific code/text |
| `Task` | Execute multi-step tasks | Complex AI-driven workflows |
| `TodoWrite` | Manage task lists | Plan and track work |

**Agent thinking:** "I can directly manipulate files, run commands, and use AI for complex reasoning."

### `claude-task-executor` Server  
**Discovered as:** High-level task interpreter
**Capabilities:** Natural language → development actions

| Tool | Agent Sees | Purpose |
|------|------------|---------|
| `execute_task_file` | Process markdown task files | Convert written tasks to actions |
| `execute_dev_cycle` | Handle natural language instructions | Interpret development requirements |

**Agent thinking:** "I can give this server high-level instructions and it will figure out what to do."

## Usage Scenarios

### Scenario 1: Agent has specific technical knowledge
**Uses:** `claude-code` directly
```python
# Agent knows exactly what to do
await session.call_tool("Read", {"file_path": "package.json"})
await session.call_tool("Edit", {"file_path": "package.json", "old_string": "1.0.0", "new_string": "1.1.0"})
await session.call_tool("Bash", {"command": "npm publish"})
```

### Scenario 2: Agent has high-level requirements
**Uses:** `claude-task-executor` first, then `claude-code`
```python
# Agent delegates planning to task executor
result = await session.call_tool("execute_dev_cycle", {
    "instructions": "Update package version and publish to npm",
    "send_progress": True
})

# Then uses the detailed plan with claude-code tools
# (The task executor guides what specific tools to use)
```

### Scenario 3: Agent processes task files
**Uses:** `claude-task-executor` for interpretation
```python
# Agent found a TODO.md file and wants to execute it
await session.call_tool("execute_task_file", {
    "file_path": "TODO.md",
    "working_directory": "/project"
})
```

## Complementary Relationship

The servers work together:

1. **`claude-task-executor`** → Interprets requirements → Recommends `claude-code` tools
2. **`claude-code`** → Executes specific operations → Reports back to agent
3. **Agent** → Orchestrates between both servers based on task complexity

## Discovery Flow for Agents

```python
# Agent connects and discovers both servers
servers = await discover_mcp_servers()

for server in servers:
    if server.name == "claude-code":
        # "I can do precise technical operations"
        technical_tools = server.tools
    
    elif server.name == "claude-task-executor":  
        # "I can handle natural language planning"
        planning_tools = server.tools

# Agent decision logic:
if task_is_specific_and_technical():
    use_claude_code_directly()
elif task_is_high_level_or_from_file():
    use_task_executor_first()
    then_use_claude_code_for_execution()
```