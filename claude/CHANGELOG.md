# Changelog

All notable changes to this project will be documented in this file.

## [1.3.0] - 2025-08-07

### Fixed
- **Critical Pydantic Validation Error**: Resolved CallToolResult content structure validation issues that caused "20 validation errors for CallToolResult" when processing task responses
- **Content Extraction Enhancement**: Added robust `extract_text_content` function to handle various result formats including tuples, dictionaries, and proper MCP objects
- **CallToolResult Format Compliance**: Ensured all CallToolResult objects include proper `isError` field and correctly formatted TextContent objects
- **Error Response Handling**: Improved error responses to maintain MCP compliance even when delegation to official Claude server fails

### Added
- Comprehensive test suite for Pydantic validation fixes (`tests/test_pydantic_fix.py`)
- Enhanced error handling for malformed responses from Claude MCP server
- Graceful handling of empty or invalid content structures
- Negative test cases for edge conditions and error scenarios

### Changed
- Enhanced documentation to reflect the Pydantic validation improvements
- Updated README.md with information about the validation fixes
- Version bumped to 1.3.0 to reflect the critical bug fix

### Technical Details
- The issue occurred when the official Claude MCP server returned content in tuple format rather than proper MCP objects
- The fix includes fallback handling for multiple content formats while maintaining strict MCP compliance
- All existing functionality remains intact with improved reliability

## [1.1.0] - 2025-08-07

### Added
- Comprehensive configuration cleanup and organization
- Detailed config-samples README with args and env specifications
- claude-desktop-bypass.json and claude-desktop-readonly.json configurations
- VERSION file for version tracking
- Enhanced documentation with complete setup examples

### Changed
- Updated all configuration file paths to use relative `./src/` structure
- Reorganized config-samples from 15 to 11 focused configurations
- Improved README with clearer quick reference tables
- Enhanced config documentation with exact command arguments and environment variables

### Removed
- 5 unnecessary/duplicate configuration files with outdated paths
- Configs with non-existent server references
- Configs with incorrect environment variables

### Fixed
- File paths in all configuration samples
- Documentation consistency across all config files
- Configuration examples now accurately reflect current project structure

## [1.0.0] - 2025-08-07

### Added
- Initial release with MCP-compliant server implementation
- Task and TodoWrite tools with full MCP progress notification support
- Comprehensive test suite (17 tests, 100% pass rate)
- Negative testing for security and validation
- Organized project structure (src/, tests/, docs/, examples/)
- 15 configuration samples for different environments
- Professional documentation and setup guides

### Features
- Complete MCP progress notification specification compliance
- Task execution with complex workflow support
- TodoWrite tool for task management
- Security validation and input sanitization
- Configurable permission modes
- Production-ready error handling