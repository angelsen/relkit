"""Build command for package distribution."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context
from ..utils import run_uv


@command("build", "Build package distribution")
def build(ctx: Context, package: Optional[str] = None) -> Output:
    """Build package distribution files."""
    # Create dist directory if it doesn't exist
    dist_dir = ctx.root / "dist"
    dist_dir.mkdir(exist_ok=True)

    # Build command with output directory
    args = ["build", "--out-dir", "dist"]

    # Add package flag if specified
    if package:
        args.extend(["--package", package])

    # Run build
    result = run_uv(args, cwd=ctx.root)

    if result.returncode != 0:
        return Output(
            success=False,
            message="Build failed",
            details=[{"type": "text", "content": result.stderr.strip()}]
            if result.stderr
            else None,
            next_steps=["Check pyproject.toml for errors"],
        )

    # Find built files
    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))

    built_files = []
    if wheels:
        built_files.append({"type": "text", "content": f"Wheel: {wheels[-1].name}"})
    if sdists:
        built_files.append({"type": "text", "content": f"Source: {sdists[-1].name}"})

    return Output(
        success=True,
        message=f"Built {ctx.name} {ctx.version}",
        details=built_files,
        data={
            "wheel": str(wheels[-1]) if wheels else None,
            "sdist": str(sdists[-1]) if sdists else None,
            "dist_dir": str(dist_dir),
        },
    )
