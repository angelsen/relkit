"""Utility functions for relkit."""

import subprocess
import json
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path


def run_git(
    args: List[str],
    cwd: Optional[Path] = None,
    capture_output: bool = True,
    check: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """
    Run git command directly, bypassing any wrappers.

    Args:
        args: Git arguments (e.g., ["status", "--porcelain"])
        cwd: Working directory for git command
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise CalledProcessError on non-zero exit
        env: Optional environment variables to set

    Returns:
        CompletedProcess result from subprocess.run

    Example:
        result = run_git(["status", "--porcelain"], cwd=ctx.root)
        if result.returncode == 0:
            changes = result.stdout.strip()
    """
    import os

    # Always use /usr/bin/git to bypass any wrappers
    cmd = ["/usr/bin/git"] + args

    # Prepare environment
    run_env = os.environ.copy() if env is None else {**os.environ, **env}

    return subprocess.run(
        cmd, cwd=cwd, capture_output=capture_output, text=True, check=check, env=run_env
    )


def run_ruff_format(
    files: Optional[List[str]] = None,
    cwd: Optional[Path] = None,
    check: bool = True,
    diff: bool = False,
) -> Dict[str, Any]:
    """
    Run ruff format command with structured output.

    Args:
        files: List of files/dirs to format (default: current dir)
        cwd: Working directory
        check: If True, only check without modifying
        diff: If True, show diff of changes

    Returns:
        Dict with:
            - success: bool
            - files_to_format: List of files needing formatting
            - total_files: int count
            - diff: Optional diff output
    """
    cmd = ["ruff", "format"]

    if check:
        cmd.append("--check")
    if diff:
        cmd.append("--diff")

    # Add files or default to current directory
    if files:
        cmd.extend(files)
    else:
        cmd.append(".")

    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    # Parse output
    output = result.stdout.strip()
    lines = output.split("\n") if output else []

    files_to_format = [
        line.replace("Would reformat: ", "")
        for line in lines
        if line.startswith("Would reformat:")
    ]

    return {
        "success": result.returncode == 0,
        "files_to_format": files_to_format,
        "total_files": len(files_to_format),
        "diff": output if diff else None,
        "raw_output": output,
    }


def run_ruff_check(
    files: Optional[List[str]] = None,
    cwd: Optional[Path] = None,
    output_format: str = "json",
    fix: bool = False,
) -> Dict[str, Any]:
    """
    Run ruff linter with structured output.

    Args:
        files: List of files/dirs to check (default: current dir)
        cwd: Working directory
        output_format: Output format (json, full, concise, etc.)
        fix: If True, apply auto-fixes

    Returns:
        Dict with:
            - success: bool
            - issues: List of issue dicts (if JSON format)
            - total_issues: int count
            - fixable: int count of auto-fixable issues
    """
    cmd = ["ruff", "check", f"--output-format={output_format}"]

    if fix:
        cmd.append("--fix")

    # Add files or default to current directory
    if files:
        cmd.extend(files)
    else:
        cmd.append(".")

    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    response = {"success": result.returncode == 0, "raw_output": result.stdout}

    # Parse JSON output if requested
    if output_format == "json" and result.stdout:
        try:
            issues = json.loads(result.stdout)
            response["issues"] = issues
            response["total_issues"] = len(issues)
            response["fixable"] = sum(1 for issue in issues if issue.get("fix"))
        except json.JSONDecodeError:
            response["issues"] = []
            response["total_issues"] = 0
            response["fixable"] = 0

    return response


def run_basedpyright(
    files: Optional[List[str]] = None,
    cwd: Optional[Path] = None,
    output_json: bool = True,
) -> Dict[str, Any]:
    """
    Run basedpyright type checker with structured output.

    Args:
        files: List of files to check (default: all project files)
        cwd: Working directory
        output_json: If True, use JSON output format

    Returns:
        Dict with:
            - success: bool (True if no errors)
            - error_count: int
            - warning_count: int
            - diagnostics: List of diagnostic dicts (if JSON)
            - summary: Dict with counts
    """
    cmd = ["basedpyright"]

    if output_json:
        cmd.append("--outputjson")

    # Add specific files if provided
    if files:
        cmd.extend(files)

    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    response = {"success": result.returncode == 0, "raw_output": result.stdout}

    # Parse JSON output
    if output_json and result.stdout:
        try:
            data = json.loads(result.stdout)
            summary = data.get("summary", {})

            response.update(
                {
                    "error_count": summary.get("errorCount", 0),
                    "warning_count": summary.get("warningCount", 0),
                    "diagnostics": data.get("generalDiagnostics", []),
                    "summary": summary,
                }
            )
        except json.JSONDecodeError:
            # Fallback to text parsing
            import re

            match = re.search(r"(\d+) errors?", result.stdout)
            response["error_count"] = int(match.group(1)) if match else 0
            response["warning_count"] = 0
            response["diagnostics"] = []
            response["summary"] = {"errorCount": response["error_count"]}

    return response


def run_uv(
    args: List[str],
    cwd: Optional[Path] = None,
    capture_output: bool = True,
    check: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """
    Run uv command with consistent interface.

    Args:
        args: uv arguments (e.g., ["sync"], ["add", "--dev", "pytest"])
        cwd: Working directory for uv command
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise CalledProcessError on non-zero exit
        env: Optional environment variables to set

    Returns:
        CompletedProcess result from subprocess.run

    Example:
        result = run_uv(["sync"], cwd=ctx.root)
        if result.returncode == 0:
            # Dependencies synced successfully
            pass

        result = run_uv(["build", "--wheel"], cwd=ctx.root)
        if result.returncode == 0:
            wheel_files = result.stdout.strip()
    """
    import os

    cmd = ["uv"] + args

    # Prepare environment
    run_env = os.environ.copy() if env is None else {**os.environ, **env}

    return subprocess.run(
        cmd, cwd=cwd, capture_output=capture_output, text=True, check=check, env=run_env
    )


def get_workspace_packages(ctx) -> List[str]:
    """
    Get list of workspace package names (excluding _root alias).

    Args:
        ctx: WorkspaceContext instance

    Returns:
        List of package names available in workspace
    """
    return [p for p in ctx.packages.keys() if p != "_root"]


def resolve_package(ctx, package: Optional[str] = None) -> Tuple[Any, Any]:
    """
    Resolve package for both workspace and single-package projects.

    Handles all the repetitive package resolution logic that appears across commands.

    Args:
        ctx: WorkspaceContext instance
        package: Optional package name

    Returns:
        Tuple of (Package object or None, Output object or None)
        - On success: (Package, None)
        - On error: (None, Output with error message)

    Example:
        target_pkg, error = resolve_package(ctx, package)
        if error:
            return error
        # Use target_pkg...
    """
    from .models import Output

    if ctx.has_workspace:
        try:
            target_pkg = ctx.require_package(package)
            return target_pkg, None
        except ValueError as e:
            return None, Output(success=False, message=str(e))
    else:
        # Single package project
        if package:
            return None, Output(
                success=False, message="--package not valid for single package project"
            )
        target_pkg = ctx.get_package()
        if not target_pkg:
            return None, Output(success=False, message="No package found in project")
        return target_pkg, None


def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse semantic version string into components.

    Args:
        version: Version string in X.Y.Z format

    Returns:
        Tuple of (major, minor, patch) integers

    Raises:
        ValueError: If version format is invalid
    """
    import re

    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def require_package_for_workspace(ctx, package: Optional[str], command_name: str):
    """
    Check if workspace requires --package parameter and return appropriate error.

    This handles the common pattern where workspace commands need --package specified.

    Args:
        ctx: WorkspaceContext instance
        package: Optional package name
        command_name: Name of the command (for error message)

    Returns:
        Output with error if package required but not provided, None otherwise

    Example:
        error = require_package_for_workspace(ctx, package, "bump")
        if error:
            return error
    """
    from .models import Output

    if ctx.has_workspace and not package:
        available = get_workspace_packages(ctx)
        return Output(
            success=False,
            message=f"Workspace requires --package for {command_name}",
            details=[
                {
                    "type": "text",
                    "content": f"Available packages: {', '.join(available)}",
                }
            ],
            next_steps=[
                f"Specify a package: relkit {command_name} --package <name>",
                "Use package name from pyproject.toml [project] section",
            ],
        )
    return None
