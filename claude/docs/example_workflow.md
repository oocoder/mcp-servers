# Step-by-Step Workflow Example

## Scenario: Agent needs to execute tasks from `project_setup.md`

### Initial Setup
**Task file (`project_setup.md`):**
```markdown
# Project Setup Tasks

## Initialize Project
- Create package.json with name "my-app"  
- Install express and nodemon as dependencies
- Create src/index.js with basic Express server

## Configure Development
- Add start script to package.json
- Create .gitignore file
- Initialize git repository

## Test Setup
- Start the development server
- Verify server responds on port 3000
```

**Available MCP Servers:**
- `claude-code`: 14 technical tools (Read, Write, Bash, etc.)
- `claude-task-executor`: 2 interpretation tools (execute_task_file, execute_dev_cycle)

---

## Step-by-Step Execution

### Step 1: Agent Discovers Servers
```python
# Agent connects to MCP
servers = await discover_mcp_servers()

# Agent sees:
# - claude-code: Technical execution tools  
# - claude-task-executor: Task interpretation tools
```

### Step 2: Agent Uses Task Executor First
```python
# Agent calls the task executor to interpret the file
result = await session.call_tool(
    server="claude-task-executor",
    tool="execute_task_file", 
    arguments={
        "file_path": "./project_setup.md",
        "working_directory": "/workspace/myproject",
        "send_progress": True
    }
)
```

**Task Executor Response:**
```
Task file read successfully: ./project_setup.md
Working directory: /workspace/myproject

Tasks to execute:
# Project Setup Tasks

## Initialize Project
- Create package.json with name "my-app"
- Install express and nodemon as dependencies  
- Create src/index.js with basic Express server

## Configure Development
- Add start script to package.json
- Create .gitignore file
- Initialize git repository

## Test Setup
- Start the development server
- Verify server responds on port 3000

Note: Use Claude MCP tools (Read, Write, Edit, Bash, etc.) to execute these tasks.
```

### Step 3: Agent Processes Instructions and Plans Execution

The agent now understands what needs to be done and uses `claude-code` tools:

#### Step 3a: Initialize Project
```python
# Create package.json
await session.call_tool(
    server="claude-code",
    tool="Write",
    arguments={
        "file_path": "/workspace/myproject/package.json",
        "content": """{
  "name": "my-app",
  "version": "1.0.0",
  "main": "src/index.js",
  "scripts": {},
  "dependencies": {},
  "devDependencies": {}
}"""
    }
)

# Install dependencies
await session.call_tool(
    server="claude-code", 
    tool="Bash",
    arguments={
        "command": "cd /workspace/myproject && npm install express nodemon",
        "description": "Install express and nodemon dependencies"
    }
)

# Create src directory and index.js
await session.call_tool(
    server="claude-code",
    tool="Bash", 
    arguments={
        "command": "mkdir -p /workspace/myproject/src",
        "description": "Create src directory"
    }
)

await session.call_tool(
    server="claude-code",
    tool="Write",
    arguments={
        "file_path": "/workspace/myproject/src/index.js", 
        "content": """const express = require('express');
const app = express();
const port = 3000;

app.get('/', (req, res) => {
  res.send('Hello World!');
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});"""
    }
)
```

#### Step 3b: Configure Development  
```python
# Add start script to package.json
current_package = await session.call_tool(
    server="claude-code",
    tool="Read",
    arguments={"file_path": "/workspace/myproject/package.json"}
)

await session.call_tool(
    server="claude-code", 
    tool="Edit",
    arguments={
        "file_path": "/workspace/myproject/package.json",
        "old_string": '"scripts": {}',
        "new_string": '"scripts": {\n    "start": "node src/index.js",\n    "dev": "nodemon src/index.js"\n  }'
    }
)

# Create .gitignore
await session.call_tool(
    server="claude-code",
    tool="Write", 
    arguments={
        "file_path": "/workspace/myproject/.gitignore",
        "content": "node_modules/\n.env\n*.log\n"
    }
)

# Initialize git
await session.call_tool(
    server="claude-code",
    tool="Bash",
    arguments={
        "command": "cd /workspace/myproject && git init",
        "description": "Initialize git repository"
    }
)
```

#### Step 3c: Test Setup
```python
# Start development server (in background)
await session.call_tool(
    server="claude-code",
    tool="Bash",
    arguments={
        "command": "cd /workspace/myproject && npm run dev &",
        "description": "Start development server"
    }
)

# Wait and test server
await session.call_tool(
    server="claude-code", 
    tool="Bash",
    arguments={
        "command": "sleep 3 && curl http://localhost:3000",
        "description": "Test server response"
    }
)
```

---

## Key Workflow Points

### 1. **Task Executor Role** (claude-task-executor)
- ✅ **Reads and parses** the markdown file
- ✅ **Interprets** natural language tasks  
- ✅ **Provides structured guidance** to the agent
- ❌ **Does NOT execute** any actual work

### 2. **Agent Role** (the AI using MCP)
- ✅ **Orchestrates** the entire workflow
- ✅ **Decides** which tools to use when
- ✅ **Translates** high-level tasks into specific tool calls
- ✅ **Handles** error conditions and retries

### 3. **Claude Code Role** (claude-code)
- ✅ **Executes** all the actual work
- ✅ **Provides** file operations, commands, AI assistance
- ✅ **Reports** results back to the agent

## Alternative: Single Server Approach

If you had **only** `claude-code`, the agent would need to:
1. Use `Read` tool to get the markdown file
2. Use `Task` tool with the file content as context
3. Let Claude figure out what to do

If you had **only** `claude-task-executor`, the agent would:
1. Get task interpretation ✅  
2. Have no way to execute the tasks ❌

## The Power of Both

Having both servers gives agents **flexibility**:
- **High-level agents**: Use task-executor for planning, claude-code for execution
- **Technical agents**: Skip task-executor, use claude-code directly  
- **File-based workflows**: Perfect for processing TODO.md, tasks.md, etc.