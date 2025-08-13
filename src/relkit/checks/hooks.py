"""Git hooks verification checks."""

import hashlib
import re
from ..models import Output, Context


# The canonical pre-commit hook content
PRECOMMIT_HOOK = """#!/bin/bash
# relkit pre-commit hook: Block direct version edits
# DO NOT EDIT - This file is managed by relkit

# Check if pyproject.toml is being committed
if git diff --cached --name-only | grep -q "pyproject.toml"; then
    # Check if version field was modified
    if git diff --cached pyproject.toml | grep -E '^\\+.*version = "' > /dev/null; then
        # Generate override hash with 60-second TTL window
        TIMESTAMP=$(date +%s)
        WINDOW=$((TIMESTAMP / 60))
        HASH=$(echo -n "$WINDOW" | sha256sum | cut -c1-8)
        
        # Check if override provided
        if [ "$HOOK_OVERRIDE" = "$HASH" ]; then
            echo "✓ Hook override accepted" >&2
            exit 0
        fi
        
        echo "✗ Direct version edit blocked by pre-commit hook" >&2
        echo "" >&2
        echo "To change version properly:" >&2
        echo "  relkit bump <major|minor|patch>" >&2
        echo "" >&2
        echo "To override this check:" >&2
        echo "  HOOK_OVERRIDE=$HASH git commit -m 'your message'" >&2
        echo "" >&2
        exit 1
    fi
fi
exit 0
"""


def get_hook_hash() -> str:
    """Get hash of current hook content."""
    return hashlib.sha256(PRECOMMIT_HOOK.encode()).hexdigest()[:8]


def get_hook_with_hash() -> str:
    """Get hook content with hash marker."""
    return PRECOMMIT_HOOK.replace(
        "# DO NOT EDIT - This file is managed by relkit",
        f"# DO NOT EDIT - This file is managed by relkit\n# Hook hash: {get_hook_hash()}",
    )


def check_hooks_initialized(ctx: Context) -> Output:
    """Check if git hooks are properly initialized."""
    hook_path = ctx.root / ".git/hooks/pre-commit"

    if not hook_path.exists():
        return Output(
            success=False,
            message="Git hooks not initialized",
            details=[
                {"type": "text", "content": "Pre-commit hook missing"},
                {
                    "type": "text",
                    "content": "Hooks ensure consistent version management",
                },
            ],
            next_steps=["Initialize hooks: relkit init-hooks"],
        )

    existing = hook_path.read_text()

    # Check if it's our hook
    if "relkit pre-commit hook" not in existing:
        return Output(
            success=False,
            message="Pre-commit hook exists but not managed by relkit",
            details=[
                {"type": "text", "content": "Another tool owns the pre-commit hook"},
                {"type": "text", "content": "Cannot verify version management"},
            ],
            next_steps=[
                "Review existing hook: cat .git/hooks/pre-commit",
                "If safe to replace: rm .git/hooks/pre-commit",
                "Then run: relkit init-hooks",
            ],
        )

    # Check hash
    match = re.search(r"# Hook hash: ([a-f0-9]{8})", existing)
    current_hash = match.group(1) if match else None
    expected_hash = get_hook_hash()

    if current_hash != expected_hash:
        return Output(
            success=False,
            message="Git hook needs updating",
            details=[
                {
                    "type": "text",
                    "content": f"Current hash: {current_hash or 'unknown'}",
                },
                {"type": "text", "content": f"Expected hash: {expected_hash}"},
                {
                    "type": "text",
                    "content": "Hook logic has changed in this version of relkit",
                },
            ],
            next_steps=["Update hook: relkit init-hooks"],
        )

    return Output(
        success=True,
        message="Git hooks properly initialized",
        details=[{"type": "text", "content": f"Hook hash: {expected_hash}"}],
    )
