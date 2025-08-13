"""Version command for testing the patterns."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context


@command("version", "Show project version")
def show_version(ctx: Context, package: Optional[str] = None) -> Output:
    """Display the version of the project or a specific package."""
    if package and ctx.is_workspace:
        # For now, just show the main version
        # In a real implementation, we'd look up the package version
        return Output(
            success=True,
            message=f"Package '{package}' version lookup not yet implemented",
            details=[
                {"type": "text", "content": f"Main project: {ctx.name} v{ctx.version}"}
            ],
        )

    version_info = f"{ctx.name}: {ctx.version}"

    return Output(
        success=True,
        message=version_info,
        data={"name": ctx.name, "version": ctx.version, "type": ctx.type},
    )
