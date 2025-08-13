"""Publish command for PyPI."""

from typing import Optional
import subprocess as sp
import os
from ..decorators import command
from ..models import Output, Context
from ..safety import requires_confirmation
from ..utils import run_uv, run_git


@command("publish", "Publish to PyPI")
@requires_confirmation(
    "publish", ttl=300, skip_private=True
)  # 5 min TTL, skip for private
def publish(ctx: Context, package: Optional[str] = None) -> Output:
    """Publish package to PyPI with safety checks."""
    # Opinionated: require version to be tagged before publishing
    expected_tag = f"v{ctx.version}"
    tag_result = run_git(["tag", "-l", expected_tag], cwd=ctx.root)

    if not tag_result.stdout.strip():
        return Output(
            success=False,
            message=f"Version {ctx.version} not tagged",
            details=[
                {"type": "text", "content": f"Expected tag: {expected_tag}"},
                {"type": "text", "content": "Publishing requires a git tag"},
                {"type": "text", "content": "This ensures releases are traceable"},
            ],
            next_steps=[
                "Create tag: relkit tag",
                "Or run full workflow: relkit release",
            ],
        )

    # Check if dist/ exists and has files
    dist_path = ctx.root / "dist"
    if not dist_path.exists():
        return Output(
            success=False,
            message="No dist directory found",
            next_steps=["Run: relkit build"],
        )

    wheels = list(dist_path.glob("*.whl"))
    sdists = list(dist_path.glob("*.tar.gz"))

    if not wheels and not sdists:
        return Output(
            success=False,
            message="No distributions found to publish",
            next_steps=["Run: relkit build"],
        )

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
        message=f"Published {ctx.name} {ctx.version} to PyPI",
        details=[
            {"type": "text", "content": f"Published: {f}"} for f in files_published
        ],
        data={
            "version": ctx.version,
            "files": files_published,
            "public": ctx.is_public,
        },
    )
