#!/usr/bin/env python3
"""
Verification script to diagnose PDF Processor MCP Server setup issues.
Run this script to check if all dependencies are installed correctly.
"""

import sys
import subprocess
from pathlib import Path

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)

def check_python_version():
    """Check if Python version is compatible"""
    print("\n[1/6] Checking Python version...")
    version = sys.version_info
    print(f"   Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("   ✗ ERROR: Python 3.8+ required")
        return False

    print("   ✓ Python version is compatible")
    return True

def check_dependencies():
    """Check if required dependencies are installed"""
    print("\n[2/6] Checking required dependencies...")

    required_packages = [
        ("mcp", "MCP SDK"),
        ("aiohttp", "Async HTTP client"),
        ("aiofiles", "Async file operations"),
        ("bs4", "BeautifulSoup4 (HTML parsing)"),
        ("fitz", "PyMuPDF (PDF processing)"),
        ("lxml", "XML/HTML processing")
    ]

    missing = []
    installed = []

    for package, description in required_packages:
        try:
            __import__(package)
            print(f"   ✓ {description} ({package})")
            installed.append(package)
        except ImportError:
            print(f"   ✗ {description} ({package}) - NOT INSTALLED")
            missing.append(package)

    # Check optional marker-pdf
    try:
        __import__("marker")
        print(f"   ✓ marker-pdf (enhanced PDF processing) - OPTIONAL")
        installed.append("marker")
    except ImportError:
        print(f"   ⚠ marker-pdf (enhanced PDF processing) - OPTIONAL (not installed)")

    if missing:
        print(f"\n   ✗ Missing {len(missing)} required dependencies")
        return False
    else:
        print(f"\n   ✓ All {len(required_packages)} required dependencies are installed")
        return True

def check_mcp_config():
    """Check if MCP config file exists and is valid"""
    print("\n[3/6] Checking MCP configuration...")

    config_path = Path(__file__).parent / "mcp-config.json"

    if not config_path.exists():
        print(f"   ✗ MCP config not found at: {config_path}")
        return False

    print(f"   ✓ MCP config found at: {config_path}")

    # Try to parse JSON
    try:
        import json
        with open(config_path) as f:
            config = json.load(f)

        # Verify structure
        if "mcpServers" not in config:
            print("   ✗ Invalid config: missing 'mcpServers' key")
            return False

        if "pdf-processor" not in config["mcpServers"]:
            print("   ✗ Invalid config: missing 'pdf-processor' server")
            return False

        server_config = config["mcpServers"]["pdf-processor"]

        # Check command path
        args = server_config.get("args", [])
        if args:
            server_path = Path(args[0])
            if not server_path.exists():
                print(f"   ✗ Server script not found: {server_path}")
                return False
            print(f"   ✓ Server script exists: {server_path}")

        print("   ✓ MCP configuration is valid")
        return True

    except Exception as e:
        print(f"   ✗ Error reading config: {e}")
        return False

def check_server_script():
    """Check if server script exists and can be imported"""
    print("\n[4/6] Checking server script...")

    server_path = Path(__file__).parent / "src" / "mcp_pdf_server.py"

    if not server_path.exists():
        print(f"   ✗ Server script not found: {server_path}")
        return False

    print(f"   ✓ Server script found: {server_path}")

    # Try to import (only if dependencies are available)
    try:
        sys.path.insert(0, str(server_path.parent))
        import mcp_pdf_server
        print("   ✓ Server script can be imported successfully")

        # Check for required components
        if not hasattr(mcp_pdf_server, 'server'):
            print("   ✗ Server object not found in script")
            return False

        if not hasattr(mcp_pdf_server, 'PDFProcessor'):
            print("   ✗ PDFProcessor class not found in script")
            return False

        print("   ✓ Server components are present")
        return True

    except ImportError as e:
        print(f"   ✗ Cannot import server (likely due to missing dependencies): {e}")
        return False
    except Exception as e:
        print(f"   ✗ Error checking server script: {e}")
        return False

def check_cache_directory():
    """Check if cache directory exists or can be created"""
    print("\n[5/6] Checking cache directory...")

    cache_dir = Path(__file__).parent / "cache"

    try:
        cache_dir.mkdir(exist_ok=True)
        print(f"   ✓ Cache directory: {cache_dir}")

        # Check write permissions
        test_file = cache_dir / ".test"
        test_file.touch()
        test_file.unlink()
        print("   ✓ Cache directory is writable")

        return True
    except Exception as e:
        print(f"   ✗ Cache directory error: {e}")
        return False

def check_mcp_protocol():
    """Check if server can respond to MCP protocol"""
    print("\n[6/6] Testing MCP protocol communication...")

    try:
        import asyncio
        import json
        import subprocess

        server_path = Path(__file__).parent / "src" / "mcp_pdf_server.py"

        async def test():
            try:
                # Start server process
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(server_path),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # Send initialize request
                request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"}
                    }
                }

                process.stdin.write((json.dumps(request) + "\n").encode())
                await process.stdin.drain()

                # Wait for response with timeout
                response_line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=3.0
                )

                if not response_line:
                    stderr = await process.stderr.read()
                    print(f"   ✗ No response from server. Error: {stderr.decode()}")
                    process.kill()
                    return False

                response = json.loads(response_line.decode())

                if "result" in response and "serverInfo" in response["result"]:
                    print(f"   ✓ Server responded correctly")
                    print(f"   ✓ Server name: {response['result']['serverInfo'].get('name')}")
                    process.kill()
                    return True
                else:
                    print(f"   ✗ Unexpected response: {response}")
                    process.kill()
                    return False

            except asyncio.TimeoutError:
                print("   ✗ Server response timeout")
                process.kill()
                return False
            except Exception as e:
                print(f"   ✗ Protocol test error: {e}")
                return False

        result = asyncio.run(test())
        return result

    except Exception as e:
        print(f"   ✗ Cannot test MCP protocol: {e}")
        return False

def print_installation_instructions():
    """Print instructions for fixing common issues"""
    print("\n" + "=" * 60)
    print("INSTALLATION INSTRUCTIONS")
    print("=" * 60)

    print("\nTo install required dependencies:")
    print("\n  Option 1: Install to user site-packages")
    print("  $ pip install --user -r mcp_requirements.txt")

    print("\n  Option 2: Create a virtual environment (recommended)")
    print("  $ python3 -m venv venv")
    print("  $ source venv/bin/activate  # On Windows: venv\\Scripts\\activate")
    print("  $ pip install -r mcp_requirements.txt")

    print("\n  Note: If using a virtual environment, update mcp-config.json")
    print("  to use the venv Python: /path/to/venv/bin/python3")

    print("\nFor Claude Code integration:")
    print("  $ claude code --mcp-config /path/to/pdf-processor/mcp-config.json")

    print("\nFor enhanced academic paper processing (optional):")
    print("  $ pip install marker-pdf")

def main():
    """Run all checks"""
    print_header("PDF Processor MCP Server - Setup Verification")
    print("This script will check if your MCP server is configured correctly.")

    results = []

    # Run all checks
    results.append(("Python Version", check_python_version()))
    results.append(("Dependencies", check_dependencies()))
    results.append(("MCP Config", check_mcp_config()))
    results.append(("Server Script", check_server_script()))
    results.append(("Cache Directory", check_cache_directory()))

    # Only test protocol if basic checks pass
    if all(r[1] for r in results):
        results.append(("MCP Protocol", check_mcp_protocol()))

    # Print summary
    print_header("VERIFICATION SUMMARY")

    all_passed = True
    for check_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All checks passed! Your MCP server is ready to use.")
        print("\nYou can now use it with Claude Code:")
        print("  $ claude code --mcp-config /path/to/pdf-processor/mcp-config.json")
        return 0
    else:
        print("❌ Some checks failed. See instructions below to fix the issues.")
        print_installation_instructions()
        return 1

if __name__ == "__main__":
    sys.exit(main())
