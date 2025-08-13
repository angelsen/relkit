# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Two-phase lockfile handling in bump command to ensure lockfile is included in tagged commits

### Changed

### Fixed

### Removed

## [1.0.2] - 2025-08-13

### Added
- New check modules for better separation of concerns:
  - `checks/changelog.py` - Centralized changelog validation
  - `checks/version.py` - Version format, tagging, and progression checks
  - `checks/distribution.py` - Build and distribution file validation
- Enhanced `checks/git.py` with additional validation functions
- Comprehensive validation functions available to all commands

### Changed
- Refactored validation logic from commands to centralized check modules
- Improved separation of concerns - each check module owns its domain
- Updated all commands to use centralized checks instead of inline validation

### Fixed

### Removed

## [1.0.1] - 2025-08-13

### Added
- Changelog enforcement in bump command - blocks if commits exist but changelog is empty

### Changed

### Fixed
- Bump command now generates HOOK_OVERRIDE internally to handle pre-commit hook

### Removed

## [1.0.0] - 2025-08-13

### Added

### Changed
- **BREAKING**: Made `bump` command atomic - now handles version, changelog, commit, tag, and push in one operation
- Bump now requires clean git state (no uncommitted changes)

### Fixed

### Removed
- **BREAKING**: Removed standalone `tag` command - functionality merged into `bump`

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
