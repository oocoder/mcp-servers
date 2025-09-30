#!/bin/bash
# Clean test runner that suppresses external dependency warnings.
# Use this script to run tests without seeing irrelevant deprecation warnings.

export PYTHONWARNINGS="ignore:builtin type.*has no.*module.*attribute:DeprecationWarning,ignore:Support for class-based.*config.*is deprecated:DeprecationWarning,ignore::DeprecationWarning:.*importlib.*,ignore::DeprecationWarning:.*pydantic.*"

exec pytest "$@"