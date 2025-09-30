#!/usr/bin/env python3
"""
Deprecation Warning Management for PDF Processor Project

This module documents and manages deprecation warnings in the codebase following best practices:
- Fix our own code warnings immediately
- Document external dependency suppressions
- Regularly review and update suppression justifications

USAGE:
- For clean test runs: Use scripts/test_clean.sh instead of direct pytest
- The environment variable approach is necessary for warnings from Python bootstrap/importlib
- Regular pytest.ini filters handle most cases, but some early warnings need env suppression

Last reviewed: 2024-08-09
Next review: 2024-11-03 (quarterly)
"""

import warnings
from typing import Dict, List


class WarningCategories:
    """Categorization of deprecation warnings by priority and action needed"""
    
    # Our code - Fix immediately
    OWN_CODE = "own_code"
    
    # Direct dependencies - Check for updates
    DIRECT_DEPS = "direct_dependencies"
    
    # External/transitive - Safe to suppress
    EXTERNAL = "external_dependencies"


WARNING_INVENTORY: Dict[str, Dict] = {
    "pydantic_class_config": {
        "category": WarningCategories.DIRECT_DEPS,
        "message": "Support for class-based `config` is deprecated",
        "module": "pydantic.*",
        "action": "Monitor Pydantic v3 migration timeline",
        "justification": "Pydantic v2 deprecation - will be removed in v3. No immediate action needed as v3 is not yet stable.",
        "review_date": "2024-11-03",
        "suppress": True
    },
    
    "swig_all_types": {
        "category": WarningCategories.EXTERNAL,
        "message": r"builtin type .* has no __module__ attribute",
        "module": ".*",  # Broader match for frozen importlib warnings
        "action": "No action - external C bindings",
        "justification": "SWIG-generated Python bindings issue from marker-pdf dependencies. Cannot be fixed at our level.",
        "review_date": "2025-02-03",  # Less frequent review
        "suppress": True
    }
}


def apply_warning_filters() -> None:
    """
    Apply documented warning filters for external dependencies.
    
    Call this function at the start of your application or test suite
    to suppress known external deprecation warnings.
    """
    
    # Apply broad patterns that catch variations in warning messages
    for warning_id, config in WARNING_INVENTORY.items():
        if config["suppress"] and config["category"] != WarningCategories.OWN_CODE:
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
                message=config["message"]
            )
    
    # Additional broad filters to catch edge cases
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*importlib.*")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=".*pydantic.*")
    
    # Comprehensive SWIG warnings patterns (multiple variations)
    swig_patterns = [
        r"builtin type .* has no __module__ attribute",
        r"builtin type SwigPyPacked has no __module__ attribute",
        r"builtin type SwigPyObject has no __module__ attribute", 
        r"builtin type swigvarlink has no __module__ attribute"
    ]
    
    for pattern in swig_patterns:
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            message=pattern
        )
    
    # Also catch any remaining SWIG warnings by broader matching
    warnings.filterwarnings(
        "ignore", 
        category=DeprecationWarning,
        message=".*Swig.*"
    )
    
    # Additional Pydantic patterns
    warnings.filterwarnings(
        "ignore",
        "Support for class-based.*config.*is deprecated",
        DeprecationWarning
    )


def get_suppression_summary() -> List[str]:
    """Get a summary of currently suppressed warnings for documentation"""
    
    suppressed = [
        f"- {warning_id}: {config['justification']}"
        for warning_id, config in WARNING_INVENTORY.items()
        if config["suppress"]
    ]
    
    return [
        "Currently suppressed deprecation warnings:",
        *suppressed,
        f"\nNext review scheduled: {min(c['review_date'] for c in WARNING_INVENTORY.values())}"
    ]


if __name__ == "__main__":
    # Print current suppression status
    for line in get_suppression_summary():
        print(line)