# Issue Creation

Create structured GitHub issues with enforced quality standards.

## Commands

### Create Bug Report
```bash
gh issue create --title "fix: description" --type bug
```

### Create Feature Request
```bash
gh issue create --title "add: description" --type feature
```

### Submit Template
```bash
gh issue submit <template-id>
```

## Requirements

- **Title**: Lowercase, max 72 chars
- **Paths**: Must use repo-relative paths (e.g., `src/relkit/commands/bump.py:174`)
- **Bugs**: Require `--error` or reproduction steps
- **Features**: Require example code
- **Formatting**: Bullets (`-`) for lists, checkboxes (`- [ ]`) for tasks

## Workflow

1. Run `gh issue create` → Creates template with instructions
2. Edit template file with proper content
3. Run `gh issue submit` → Validates and creates issue

The wrapper enforces structure, validates paths exist, and adds commit context automatically.