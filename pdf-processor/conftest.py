#!/usr/bin/env python3
"""
Pytest configuration for PDF processor project.

Applies warning management filters before test collection.
See warning_management.py for detailed documentation.
"""

import os
import warnings
import pytest

# Set environment variable to suppress warnings at Python startup
# Note: Only use standard warning categories that Python recognizes
if 'PYTHONWARNINGS' not in os.environ:
    os.environ['PYTHONWARNINGS'] = (
        'ignore:builtin type.*has no.*module.*attribute:DeprecationWarning,'
        'ignore:Support for class-based.*config.*is deprecated:DeprecationWarning,'
        'ignore::DeprecationWarning:.*importlib.*,'
        'ignore::DeprecationWarning:.*pydantic.*'
    )

# Apply filters immediately at module level
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r"builtin type .* has no __module__ attribute")
warnings.filterwarnings("ignore", category=DeprecationWarning, message="Support for class-based.*config.*is deprecated")
warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*importlib.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*pydantic.*")


def pytest_configure(config):
    """Configure pytest with our warning management strategy"""
    
    # Import and apply centralized warning management
    try:
        from scripts.warning_management import apply_warning_filters
        apply_warning_filters()
    except ImportError:
        # Fallback to inline filters if warning_management is not available
        _apply_fallback_filters()
    
    # Always show warnings for our own code modules (highest priority)
    _enable_own_code_warnings()


def _apply_fallback_filters():
    """Apply fallback warning filters if warning_management module is not available"""
    # Suppress SWIG-related warnings from marker-pdf dependencies
    # These come from frozen importlib during Python startup
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r"builtin type .* has no __module__ attribute"
    )
    
    # Suppress Pydantic v2 deprecation warnings
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r"Support for class-based.*config.*is deprecated"
    )
    
    # Also suppress them by module to catch edge cases
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*importlib.*")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*pydantic.*")


def _enable_own_code_warnings():
    """Enable warnings for our own code modules"""
    own_modules = ["mcp_pdf_server.*", "tests.*", "quick_marker_test.*"]
    for module in own_modules:
        warnings.filterwarnings("always", category=DeprecationWarning, module=module)


def pytest_sessionstart(session):
    """Print warning management summary at test session start"""
    try:
        from scripts.warning_management import get_suppression_summary
        print("\n" + "="*60)
        print("DEPRECATION WARNING MANAGEMENT")
        print("="*60)
        for line in get_suppression_summary():
            print(line)
        print("="*60)
    except ImportError:
        print("\n" + "="*60)
        print("DEPRECATION WARNING MANAGEMENT")
        print("="*60)
        print("Using fallback warning filters (warning_management module not found)")
        print("="*60)


def pytest_sessionfinish(session, exitstatus):
    """Apply warning filters one final time before session ends"""
    # Reapply filters to catch any late warnings
    _apply_fallback_filters()
    
    # Also suppress any remaining sys warnings
    import sys
    if hasattr(sys, 'modules'):
        for module_name in list(sys.modules.keys()):
            if any(pattern in module_name for pattern in ['swig', 'pydantic', 'importlib']):
                warnings.filterwarnings("ignore", category=DeprecationWarning, module=module_name)