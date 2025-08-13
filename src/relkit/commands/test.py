"""Test command for built packages."""

from typing import Optional
import subprocess as sp
from ..decorators import command
from ..models import Output, Context


@command("test", "Test built package in isolated environment")
def test(ctx: Context, package: Optional[str] = None) -> Output:
    """Test built package in an isolated environment."""
    # Find wheel in dist/
    dist_dir = ctx.root / "dist"

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
    # Use the package name with underscores (relkit) for import
    import_name = ctx.name.replace("-", "_")

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
        message=f"Package {ctx.name} tested successfully",
        details=details,
        data={"wheel": str(wheel_path), "import_name": import_name},
    )
