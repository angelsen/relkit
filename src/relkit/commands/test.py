"""Test command for built packages."""

from ..decorators import command
from ..models import Output, Context
from ..utils import run_uv


@command("test", "Test built package in isolated environment")
def test(ctx: Context, package: str | None = None) -> Output:
    """Test built package in an isolated environment."""
    # Set package context if provided
    if package:
        ctx = ctx.with_package(package)

    # Get the target package (will raise if workspace needs --package)
    try:
        ctx.package  # Validate package exists
    except ValueError as e:
        return Output(success=False, message=str(e))

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
    import_name = ctx.package.import_name

    # Use run_uv utility for consistency
    args = [
        "run",
        "--isolated",
        "--with",
        str(wheel_path),
        "python",
        "-c",
        f"import {import_name}; print('Successfully imported {import_name}')",
    ]

    result = run_uv(args, cwd=ctx.root)

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
        message=f"Package {ctx.package.name} tested successfully",
        details=details,
        data={"wheel": str(wheel_path), "import_name": import_name},
    )
