"""Test command for built packages."""

from typing import Optional
import subprocess as sp
from ..decorators import command
from ..models import Output, Context


@command("test", "Test built package in isolated environment")
def test(ctx: Context, package: Optional[str] = None) -> Output:
    """Test built package in an isolated environment."""
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
                next_steps=["Specify package: relkit test --package <name>"],
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

    # Find wheel in package-specific dist/
    dist_dir = ctx.get_dist_path(package)

    if not dist_dir.exists():
        return Output(
            success=False,
            message="No dist directory found",
            next_steps=["Run: relkit build"],
        )

    # Find the most recent wheel
    wheels = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime)

    if not wheels:
        return Output(
            success=False,
            message="No wheel found in dist/",
            next_steps=["Run: relkit build"],
        )

    wheel_path = wheels[-1]

    # Test import in isolated environment
    import_name = target_pkg.import_name

    cmd = [
        "uv",
        "run",
        "--isolated",
        "--with",
        str(wheel_path),
        "python",
        "-c",
        f"import {import_name}; print('Successfully imported {import_name}')",
    ]

    result = sp.run(cmd, capture_output=True, text=True, cwd=ctx.root)

    if result.returncode != 0:
        return Output(
            success=False,
            message=f"Failed to import {import_name} from wheel",
            details=[
                {"type": "text", "content": f"Wheel: {wheel_path.name}"},
                {"type": "text", "content": "Error:"},
                {
                    "type": "text",
                    "content": result.stderr.strip()
                    if result.stderr
                    else "Unknown error",
                },
            ],
        )

    details = [
        {"type": "text", "content": f"Wheel: {wheel_path.name}"},
        {"type": "text", "content": f"Import: {import_name} successful"},
    ]
    if result.stdout:
        details.append({"type": "text", "content": f"Output: {result.stdout.strip()}"})

    return Output(
        success=True,
        message=f"Package {target_pkg.name} tested successfully",
        details=details,
        data={"wheel": str(wheel_path), "import_name": import_name},
    )
