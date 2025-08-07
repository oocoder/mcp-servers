#!/usr/bin/env python3
"""
Direct test of the task execution logic.
"""

import subprocess
import os

def test_execute_dev_cycle():
    """Test the development cycle execution directly."""
    
    instructions = "Create a simple Python script that prints 'Hello from task executor!' and save it as test_output.py"
    working_dir = "/Users/alexmaldonado/projects/mcp-servers/claude"
    
    try:
        # Execute development cycle using Claude
        claude_cmd = [
            "claude", "--",
            f"Execute this development cycle in directory {working_dir}:\n\n{instructions}"
        ]
        
        result = subprocess.run(
            claude_cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print("Command:", " ".join(claude_cmd))
        print(f"Working directory: {working_dir}")
        print(f"Exit code: {result.returncode}")
        
        if result.stdout:
            print(f"Output:\n{result.stdout}")
        if result.stderr:
            print(f"Errors:\n{result.stderr}")
        
        # Check if file was created
        output_file = os.path.join(working_dir, "test_output.py")
        if os.path.exists(output_file):
            print(f"\n✅ Success: {output_file} was created!")
            with open(output_file, 'r') as f:
                print("File contents:")
                print(f.read())
        else:
            print(f"\n❌ File {output_file} was not created")
            
    except subprocess.TimeoutExpired:
        print("❌ Task execution timed out")
    except Exception as e:
        print(f"❌ Error executing development cycle: {str(e)}")

if __name__ == "__main__":
    test_execute_dev_cycle()