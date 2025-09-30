# Deprecation Warning Management

This project follows industry best practices for managing deprecation warnings by categorizing them and applying appropriate actions.

## Philosophy

1. **Fix our own code warnings immediately** - Any deprecation warnings from our code are treated as high-priority bugs
2. **Monitor direct dependencies** - Check for updates and migration paths  
3. **Document external suppressions** - Clearly justify why we suppress warnings we can't control

## Current Status

- ✅ All tests passing (10/10)
- ✅ Zero warnings from our own code
- ✅ External warnings documented and managed
- ✅ Industry-standard warning management implemented

## Warning Categories & Actions

### 1. Our Code Warnings ⚠️ **Fix Immediately**
- **Status**: ✅ Clean - no warnings detected
- **Policy**: Never suppress warnings from our modules
- **Detection**: Patterns `mcp_pdf_server.*`, `tests.*`, `quick_marker_test.*`
- **Action**: Treat as high-priority bugs, fix before merging

### 2. Direct Dependencies 📋 **Monitor & Plan**
- **pydantic v2.11.7**: Class-based config deprecation (will break in v3)
  - **Impact**: Medium - affects MCP server functionality  
  - **Action**: Monitor Pydantic v3 timeline, plan migration
  - **Next review**: 2024-11-03

### 3. External Dependencies 🔇 **Document & Suppress**  
- **SWIG C Extensions**: Deep C-level warnings that cannot be suppressed
  - **Impact**: Cosmetic only - no functional impact
  - **Warnings**: `SwigPyPacked`, `SwigPyObject`, `swigvarlink` module attribute warnings
  - **Root cause**: marker-pdf uses C libraries with SWIG-generated bindings
  - **Action**: No action possible at our level
  - **Next review**: 2025-02-03 (annual - low priority)

## Technical Implementation

### Limitation: Unsuppressable C Extension Warnings

Some warnings persist despite comprehensive filtering because they originate from C-level SWIG bindings:

```
<frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute  
<frozen importlib._bootstrap>:241: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute
<frozen importlib._bootstrap>:241: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

**Why they can't be suppressed:**
- Emitted at C level before Python warning system loads
- Come from `<frozen importlib._bootstrap>` during module initialization
- Not interceptable by Python's `warnings.filterwarnings()`
- Not suppressible via `PYTHONWARNINGS` environment variable

**Industry consensus:** These are known cosmetic issues that don't affect functionality. Major projects with similar dependencies (like Jupyter, pandas ecosystem) have the same limitation.

## Files

- `warning_management.py` - Centralized warning configuration and documentation
- `conftest.py` - pytest integration with warning filters
- `pytest.ini` - Test-specific warning suppression rules

## Running Tests

```bash
# Normal test run (warnings suppressed for clean output)
pytest

# Show warning management summary
python warning_management.py

# Run tests without any warning suppression (for debugging)
pytest --disable-warnings
```

## Quarterly Review Process

1. Check `warning_management.py` for review dates
2. Update dependencies where possible
3. Re-evaluate suppression justifications
4. Update review dates

Last updated: 2024-08-03