"""Publish command for PyPI."""

from typing import Optional
import subprocess as sp
import os
from ..decorators import command
from ..models import Output, Context
from ..safety import requires_confirmation, requires_active_decision
from ..utils import run_uv
from ..checks.version import check_version_tagged
from ..checks.distribution import check_dist_has_files, check_build_token_valid


@command("publish", "Publish to PyPI")
@requires_active_decision(
    "publish_build",
    checks=[check_build_token_valid],  # Ensure publishing exact built files
)
@requires_confirmation(
    "publish", ttl=300, skip_private=True
)  # 5 min TTL, skip for private
def publish(ctx: Context, package: Optional[str] = None) -> Output:
    """Publish package to PyPI with safety checks."""
    # Handle workspace packages
    if ctx.has_workspace:
        if not package:
            return Output(
                success=False,
                message="Workspace requires --package",
                details=[
                    {
                        "type": "text",
                        "content": f"Available: {', '.join([p for p in ctx.packages.keys() if p != '_root'])}",
                    }
                ],
                next_steps=["Specify package: relkit publish --package <name>"],
            )
        try:
            target_pkg = ctx.require_package(package)
        except ValueError as e:
            return Output(success=False, message=str(e))
    else:
        if package:
            return Output(
                success=False, message="--package not valid for single package project"
            )
        target_pkg = ctx.get_package()
        if not target_pkg:
            return Output(success=False, message="No package found in project")

    # Check if version is tagged (required for publishing)
    expected_tag = target_pkg.tag_name
    tag_check = check_version_tagged(ctx)  # Still use ctx for backward compat
    if not tag_check.success:
        return Output(
            success=False,
            message=f"Version {target_pkg.version} not tagged",
            details=[
                {"type": "text", "content": f"Expected tag: {expected_tag}"},
                {"type": "text", "content": "Publishing requires a git tag"},
                {"type": "text", "content": "This ensures releases are traceable"},
            ],
            next_steps=[
                "Use: relkit bump <major|minor|patch> to create a new release",
                "Or run full workflow: relkit release",
            ],
        )

    # Check if we have distribution files to publish
    dist_check = check_dist_has_files(ctx)
    if not dist_check.success:
        return Output(
            success=False,
            message=dist_check.message,
            details=dist_check.details,
            next_steps=dist_check.next_steps or ["Run: relkit build"],
        )

    # Get the dist files from the package directory
    dist_path = target_pkg.path / "dist"
    wheels = list(dist_path.glob("*.whl"))
    sdists = list(dist_path.glob("*.tar.gz"))

    # Try to get token from pass
    token = None
    token_result = sp.run(["pass", "pypi/uv-publish"], capture_output=True, text=True)

    if token_result.returncode == 0:
        token = token_result.stdout.strip()

    # Build command
    args = ["publish"]

    # Add files to publish
    for wheel in wheels:
        args.append(str(wheel))
    for sdist in sdists:
        args.append(str(sdist))

    # Prepare environment with token
    env = {}
    if token:
        env["UV_PUBLISH_TOKEN"] = token
    elif not os.getenv("UV_PUBLISH_TOKEN"):
        return Output(
            success=False,
            message="No PyPI token found",
            details=[
                {"type": "text", "content": "Checked: pass pypi/uv-publish"},
                {
                    "type": "text",
                    "content": "Checked: UV_PUBLISH_TOKEN environment variable",
                },
            ],
            next_steps=[
                "Set token in pass: pass insert pypi/uv-publish",
                "Or set: UV_PUBLISH_TOKEN=<token>",
            ],
        )

    # Run publish (token passed via env for security)
    result = run_uv(args, cwd=ctx.root, env=env if env else None)

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"

        # Check for common errors
        if "already exists" in error_msg.lower():
            return Output(
                success=False,
                message=f"Version {ctx.version} already exists on PyPI",
                details=[{"type": "text", "content": error_msg}],
                next_steps=[
                    "Bump version: relkit bump <major|minor|patch>",
                    "Then rebuild: relkit build",
                ],
            )

        return Output(
            success=False,
            message="Failed to publish",
            details=[{"type": "text", "content": error_msg}],
            next_steps=[
                "Check PyPI token is valid",
                "Ensure you have upload permissions",
            ],
        )

    files_published = [f.name for f in wheels] + [f.name for f in sdists]

    return Output(
        success=True,
        message=f"Published {target_pkg.name} {target_pkg.version} to PyPI",
        details=[
            {"type": "text", "content": f"Published: {f}"} for f in files_published
        ],
        data={
            "version": target_pkg.version,
            "files": files_published,
            "public": ctx.is_public,
        },
    )
