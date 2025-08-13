# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.1.2] - 2025-08-13

### Added
- Changelog version check in tag command to prevent re-releasing versions
- Remote repository requirement for tag creation
- Tag requirement for publishing to PyPI
- 60-second TTL for hook override system

### Changed
- Renamed project from uv-pm to relkit
- Updated description to "Opinionated release toolkit for modern Python projects"

### Fixed
- Type checking error display format (now uses proper dict structure)
- Pre-commit hook escape sequence warning

### Removed

## [0.1.1] - 2025-08-13

### Added
- Initial release of relkit - opinionated project manager for modern Python projects
- Complete release workflow management (bump, build, test, tag, publish)
- Git hooks for version management and conventional commits
- Comprehensive quality checks (formatting, linting, type checking)
- Safety tokens for destructive operations
- Support for single packages, workspaces, and hybrid projects
- PyPI publishing with configurable index URLs
- Automated changelog management

### Changed
- N/A (initial release)

### Fixed
- N/A (initial release)

### Removed
- N/A (initial release)

<!-- 
When you run 'relkit bump', the [Unreleased] section will automatically 
become the new version section. Make sure to add your changes above!
-->
