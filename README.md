# relkit: Opinionated Release Toolkit for Modern Python Projects

**"This Way or No Way"** - A strict, opinionated release workflow enforcer for Python projects using uv.

## Features

- 🚀 **Workspace Support**: Per-package versioning in monorepos
- 🔒 **Atomic Releases**: Version, changelog, commit, tag, and push in one command
- 🎯 **Explicit Operations**: No magic, every action is intentional
- ✅ **Pre-flight Checks**: Validates everything before release
- 📝 **Changelog Enforcement**: Required for all releases
- 🏷️ **Smart Tagging**: `v1.0.0` for single packages, `package-v1.0.0` for workspaces
- 🚫 **Safety First**: Blocks dangerous operations before they happen

## Installation

```bash
# Add to your project as a dev dependency
uv add --dev relkit

# Or install from GitHub
uv add --dev git+https://github.com/angelsen/relkit.git
```

## Quick Start

### Single Package Projects

```bash
# Initialize git hooks (recommended)
relkit init-hooks

# Check project status
relkit status

# Make changes, update CHANGELOG.md, then bump version
relkit bump patch  # or minor/major

# Full release workflow
relkit release
```

### Workspace Projects

```bash
# Show workspace overview
relkit status

# Work with specific packages (--package is required)
relkit status --package termtap
relkit bump patch --package termtap
relkit build --package termtap
relkit publish --package termtap

# Package-specific tags are created automatically
# e.g., termtap-v1.0.0, webtap-v2.1.0
```

## Commands

### Core Commands

- `relkit status [--package NAME]` - Show release readiness
- `relkit bump <major|minor|patch> [--package NAME]` - Atomic version bump with changelog, commit, and tag
- `relkit release [--package NAME]` - Complete release workflow
- `relkit version` - Show current version

### Build & Publish

- `relkit build [--package NAME]` - Build distribution packages
- `relkit test` - Test built packages
- `relkit publish [--package NAME]` - Publish to PyPI (requires confirmation)

### Development Tools

- `relkit check <all|git|changelog|format|lint|types> [--fix]` - Run quality checks
- `relkit init-hooks` - Install git hooks

### Git Wrappers

- `relkit git <command>` - Pass-through to git with awareness

## Workspace Support

Relkit seamlessly handles three project types:

### 1. Single Package (default)
```toml
[project]
name = "mypackage"
version = "1.0.0"
```
- Commands work without `--package` flag
- Tags: `v1.0.0`

### 2. Pure Workspace
```toml
[tool.uv.workspace]
members = ["packages/*"]
# No [project] section in root
```
- All commands require `--package` flag
- Tags: `package-v1.0.0`

### 3. Hybrid Workspace
```toml
[project]
name = "root-package"
version = "2.0.0"

[tool.uv.workspace]
members = ["packages/*"]
```
- Root package and workspace members
- Use `--package root-package` or `--package member-name`
- Tags: `v2.0.0` for root, `member-v1.0.0` for members

## Philosophy

### Explicit Over Magic
- Workspace operations require explicit `--package` selection
- No automatic dependency cascades
- Clear errors when package selection is ambiguous

### Separation of Concerns
- **uv**: Manages dependencies and workspace setup
- **relkit**: Manages releases and versioning
- **git**: Version control (wrapped for safety)

### Atomic Operations
The `bump` command is atomic - it handles everything in one transaction:
1. Updates version in pyproject.toml
2. Updates CHANGELOG.md
3. Commits changes
4. Syncs lockfile if needed
5. Creates appropriate tag
6. Pushes to remote

## Safety Features

### Blocked Operations

❌ **Direct version edits**
```bash
# Editing version in pyproject.toml directly is blocked
git commit -am "bump version"  # BLOCKED by pre-commit hook
```

❌ **Manual tag creation**
```bash
git tag v1.0.0  # BLOCKED by git hook
# Tags must be created via: relkit bump
```

❌ **Dirty working directory**
```bash
# With uncommitted changes:
relkit bump patch  # BLOCKED - requires clean git
```

### Required Confirmations

- Publishing to PyPI requires explicit confirmation
- Major version bumps trigger breaking change warning
- All operations show clear next steps on failure

## Configuration

Relkit reads from `pyproject.toml`:

```toml
[project]
name = "your-package"
version = "0.1.0"  # Never edit directly!

[tool.uv.workspace]
members = ["packages/*"]  # Optional workspace config
```

Each package maintains its own:
- `pyproject.toml` with version
- `CHANGELOG.md` with release notes
- Git tags with appropriate naming

## Error Messages

All errors are actionable:

```
✗ Workspace requires --package

  Available packages: termtap, webtap, logtap

Next steps:
  1. Specify a package: relkit bump patch --package <name>
  2. Use package name from pyproject.toml [project] section
```

## Development

```bash
# Clone repository
git clone https://github.com/angelsen/relkit.git
cd relkit

# Install in development mode
uv sync

# Run tests
uv run pytest

# Check types
uv run pyright
```

## Contributing

This tool is intentionally opinionated. We welcome contributions that:
- Improve error messages
- Add safety checks
- Enhance workspace support
- Fix bugs

We generally reject:
- Features that add "escape hatches"
- Options to bypass safety checks
- Implicit or magical behaviors

## License

MIT

## Credits

Created by Fredrik Angelsen. Built with Python 3.12+ and uv.