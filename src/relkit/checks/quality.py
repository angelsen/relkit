"""Code quality checks."""

from ..models import Output, Context
from ..utils import run_ruff_format, run_ruff_check, run_basedpyright


def check_formatting(ctx: Context, **kwargs) -> Output:
    """Check code formatting with ruff format."""
    result = run_ruff_format(cwd=ctx.root, check=True)

    if result["success"]:
        return Output(success=True, message="Code formatting is correct")

    files = result["files_to_format"]
    total = result["total_files"]

    # Show first 10 files
    details = []
    for file in files[:10]:
        # Make paths relative to project root
        if file.startswith(str(ctx.root)):
            file = file[len(str(ctx.root)) + 1 :]
        details.append({"type": "text", "content": file})

    if total > 10:
        details.append({"type": "text", "content": f"... and {total - 10} more files"})

    return Output(
        success=False,
        message=f"{total} file(s) need formatting",
        details=details,
        next_steps=["Run: ruff format ."],
    )


def check_linting(ctx: Context, **kwargs) -> Output:
    """Check code with ruff linter."""
    result = run_ruff_check(cwd=ctx.root, output_format="json")

    if result["success"]:
        return Output(success=True, message="No linting issues found")

    issues = result.get("issues", [])
    total = result.get("total_issues", 0)
    fixable = result.get("fixable", 0)

    # Format first 10 issues for display
    details = []
    for issue in issues[:10]:
        filename = issue["filename"].replace(str(ctx.root) + "/", "")
        details.append(
            {
                "type": "text",
                "content": f"{filename}:{issue['location']['row']}:{issue['location']['column']}: "
                f"{issue['code']} {issue['message']}",
            }
        )

    if total > 10:
        details.append({"type": "text", "content": f"... and {total - 10} more issues"})

    next_steps = []
    if fixable > 0:
        next_steps.append(f"Run: ruff check --fix . (auto-fix {fixable} issues)")
    next_steps.append("Fix remaining issues manually")

    return Output(
        success=False,
        message=f"Found {total} linting issue(s)",
        details=details,
        next_steps=next_steps,
    )


def check_types(ctx: Context, **kwargs) -> Output:
    """Check types with basedpyright."""
    result = run_basedpyright(cwd=ctx.root, output_json=True)

    error_count = result.get("error_count", 0)
    warning_count = result.get("warning_count", 0)

    if error_count == 0:
        return Output(success=True, message="Type checking passed")

    # Format diagnostics for display
    diagnostics = result.get("diagnostics", [])
    details = []

    for diag in diagnostics[:10]:
        if diag.get("severity") == "error":
            filename = diag["file"].replace(str(ctx.root) + "/", "")
            line = diag["range"]["start"]["line"] + 1  # Convert to 1-based
            col = diag["range"]["start"]["character"] + 1
            details.append(
                {
                    "type": "text",
                    "content": f"{filename}:{line}:{col}: {diag['message']}",
                }
            )

    if error_count > 10:
        details.append(
            {"type": "text", "content": f"... and {error_count - 10} more errors"}
        )

    if warning_count > 0:
        details.append(
            {"type": "text", "content": f"Also found {warning_count} warning(s)"}
        )

    return Output(
        success=False,
        message=f"Type checking found {error_count} error(s)",
        details=details,
        next_steps=["Fix type errors shown above"],
    )
