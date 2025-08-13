# relkit: Opinionated Project Manager for uv

**"This Way or No Way"** - A strict, opinionated release workflow enforcer for Python projects using uv.

## Features

- 🚫 **Strict Enforcement**: No bypasses, no escape hatches
- 🔒 **Safe Releases**: Blocks dangerous operations before they happen
- 📝 **Conventional Commits**: Enforces proper commit messages
- 📋 **Changelog Management**: Required for all releases
- 🏷️ **Version Control**: Semantic versioning only
- ✅ **Pre-flight Checks**: Validates everything before release

## Installation

```bash
# Clone and install in development mode
git clone <repo-url>
cd relkit
uv sync  # Installs project in editable mode with dependencies

# Or add to your project as a dev dependency
uv add --dev relkit
```

## Quick Start

```bash
# Initialize changelog (required)
relkit init-changelog

# Install git hooks to enforce workflows
relkit install-hooks

# Make changes, then bump version
relkit bump patch  # or minor/major

# Commit (enforces conventional format)
git commit -m "feat: add new feature"

# Run pre-release checks
relkit preflight

# Full release workflow
relkit release
```

## Workflow Philosophy

This tool enforces a strict workflow with NO exceptions:

1. **Clean Git Required**: Cannot bump or release with uncommitted changes
2. **Changelog Required**: Every release must document changes
3. **No Direct Edits**: Version must be bumped via `relkit bump`
4. **Atomic Releases**: `relkit bump` handles version, changelog, commit, tag, and push atomically
5. **Conventional Commits**: All commits must follow the convention

## Commands

### Version Management
- `relkit bump <major|minor|patch>` - Atomic release: bump version, update changelog, commit, tag, and push
- `relkit version` - Show current version

### Release Workflow
- `relkit preflight` - Run all pre-release checks
- `relkit release` - Complete release workflow
- `relkit publish` - Publish to PyPI (requires confirmation)

### Development
- `relkit build` - Build distribution packages
- `relkit test` - Test built packages
- `relkit install-hooks` - Install git hooks

### Development Tools
- `relkit build` - Build distribution packages
- `relkit test` - Test built packages
- `relkit install-hooks` - Install git hooks

## Enforcement Rules

### Blocked Operations

❌ **Direct version edits in pyproject.toml**
```bash
# This will be blocked by pre-commit hook
vim pyproject.toml  # edit version = "x.x.x"
git commit -am "bump version"  # BLOCKED!
```

❌ **Creating git tags directly**
```bash
git tag v1.0.0  # BLOCKED by git hook
# Tags are created automatically by: relkit bump
```

❌ **Releasing with dirty git**
```bash
# With uncommitted changes:
relkit release  # BLOCKED!
relkit bump     # BLOCKED!
```

❌ **Releasing without changelog**
```bash
# Without changelog entry for current version:
relkit release  # BLOCKED!
```

### Enforced Standards

✅ **Conventional Commits**
```bash
# Bad - will be rejected:
git commit -m "updated stuff"

# Good - will be accepted:
git commit -m "feat: add user authentication"
git commit -m "fix(api): handle null responses"
git commit -m "chore: bump version to 1.0.0"
```

✅ **Proper Workflow**
```bash
# The ONLY way to release:
1. relkit init-changelog      # Once per project
2. # make changes
3. # update CHANGELOG.md
4. relkit bump patch
5. git commit -m "chore: bump version to x.x.x"
6. relkit release              # preflight → build → test → tag → publish
```

## Configuration

The tool reads from `pyproject.toml`:

```toml
[project]
name = "your-package"
version = "0.1.0"  # Never edit directly!

[tool.uv]
# Workspace configuration
workspace = { members = ["packages/*"] }
```

## Safety Features

- **Confirmation Tokens**: Dangerous operations require time-limited tokens
- **Force Push Protection**: Requires explicit confirmation
- **Main Branch Warnings**: Warns when pushing to main/master
- **Claude Signature Stripping**: Automatically removes AI-generated signatures

## Error Messages

All errors are clear and actionable:

```
✗ BLOCKED: Git working directory must be clean
  Found 3 uncommitted change(s):
  
  M  src/file1.py
  M  src/file2.py
  ?? new_file.py

Next steps:
  1. Commit all changes: git commit -am 'your message'
  2. Or stash them: git stash
  3. Then try again
```

## Contributing

This tool is intentionally opinionated. Feature requests for bypasses, 
overrides, or "escape hatches" will be rejected. The workflow is strict 
by design.

## License

MIT