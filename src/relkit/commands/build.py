"""Build command for package distribution."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context
from ..utils import run_uv
from ..safety import generate_content_token


@command("build", "Build package distribution")
def build(ctx: Context, package: Optional[str] = None) -> Output:
    """Build package distribution files."""
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
                next_steps=["Specify package: relkit build --package <name>"],
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

    # Create dist directory in package location
    dist_dir = target_pkg.path / "dist"
    dist_dir.mkdir(exist_ok=True)

    # Build command with package path
    args = ["build", target_pkg.path, "--out-dir", str(dist_dir)]

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

    # Generate build token tied to the exact dist contents
    # This ensures only these exact files can be published
    dist_contents = ""
    for f in sorted(dist_dir.glob("*")):
        if f.is_file() and (f.suffix in [".whl", ".gz"]):
            # Include filename, size, and modification time
            stat = f.stat()
            dist_contents += f"{f.name}:{stat.st_size}:{stat.st_mtime_ns}\n"

    # Generate token valid for 30 minutes
    build_token = generate_content_token(
        target_pkg.name,
        "build_publish",
        dist_contents,
        ttl=1800,  # 30 minutes
    )

    # Add token info to output
    built_files.extend(
        [
            {"type": "spacer"},
            {"type": "text", "content": f"✓ Build token: BUILD_PUBLISH={build_token}"},
            {
                "type": "text",
                "content": "  Valid for 30 minutes for publishing these exact files",
            },
        ]
    )

    return Output(
        success=True,
        message=f"Built {target_pkg.name} {target_pkg.version}",
        details=built_files,
        data={
            "wheel": str(wheels[-1]) if wheels else None,
            "sdist": str(sdists[-1]) if sdists else None,
            "dist_dir": str(dist_dir),
            "build_token": build_token,
        },
    )
