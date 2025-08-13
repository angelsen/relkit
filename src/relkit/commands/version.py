"""Version command showing package or project version."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context
from ..utils import resolve_package


@command("version", "Show project version")
def show_version(ctx: Context, package: Optional[str] = None) -> Output:
    """Display the version of the project or a specific package."""

    # Handle package resolution
    if package or ctx.has_workspace:
        # In workspace, allow showing specific package or default to showing workspace info
        if ctx.has_workspace and not package:
            # Show workspace overview
            from ..utils import get_workspace_packages

            packages = get_workspace_packages(ctx)

            details = [
                {"type": "text", "content": f"Workspace: {ctx.root.name}"},
            ]

            # Show root package if exists
            if "_root" in ctx.packages:
                root_pkg = ctx.packages["_root"]
                details.append(
                    {
                        "type": "text",
                        "content": f"Root: {root_pkg.name} v{root_pkg.version}",
                    }
                )

            # Show all workspace packages
            if packages:
                details.append(
                    {"type": "text", "content": f"Packages ({len(packages)}):"}
                )
                for pkg_name in sorted(packages):
                    pkg = ctx.packages[pkg_name]
                    details.append(
                        {"type": "text", "content": f"  - {pkg.name} v{pkg.version}"}
                    )

            return Output(
                success=True,
                message="Workspace versions",
                details=details,
                next_steps=["Show specific version: relkit version --package <name>"],
            )

        # Resolve specific package
        target_pkg, error = resolve_package(ctx, package)
        if error:
            return error

        return Output(
            success=True,
            message=f"{target_pkg.name}: {target_pkg.version}",
            data={
                "name": target_pkg.name,
                "version": target_pkg.version,
                "path": str(target_pkg.path),
                "is_root": target_pkg.is_root,
            },
        )

    # Single package project without --package
    version_info = f"{ctx.name}: {ctx.version}"
    return Output(
        success=True,
        message=version_info,
        data={"name": ctx.name, "version": ctx.version, "type": ctx.type},
    )
