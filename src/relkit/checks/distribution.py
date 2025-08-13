"""Distribution and build validation checks."""

import os
from typing import Optional, List, Dict, Any
from ..models import Output, Context
from ..safety import verify_content_token


def check_dist_exists(ctx: Context, package: Optional[str] = None, **kwargs) -> Output:
    """Check if dist directory exists."""
    # Get dist path with error handling
    try:
        dist_path = ctx.get_dist_path(package)
    except ValueError as e:
        return Output(success=False, message=str(e))

    if not dist_path.exists():
        return Output(
            success=False,
            message="No dist directory found",
            details=[
                {"type": "text", "content": "Build artifacts are stored in dist/"},
                {
                    "type": "text",
                    "content": "This directory is created by the build process",
                },
            ],
            next_steps=["Run: relkit build"],
        )

    if not dist_path.is_dir():
        return Output(
            success=False,
            message="dist exists but is not a directory",
            details=[
                {
                    "type": "text",
                    "content": "dist should be a directory containing build artifacts",
                },
            ],
            next_steps=[
                "Remove the file: rm dist",
                "Then build: relkit build",
            ],
        )

    return Output(success=True, message="dist directory exists")


def check_dist_has_files(
    ctx: Context, package: Optional[str] = None, **kwargs
) -> Output:
    """Check if dist directory contains distribution files."""
    # Get dist path with error handling
    try:
        dist_path = ctx.get_dist_path(package)
    except ValueError as e:
        return Output(success=False, message=str(e))

    # First check if dist exists
    exists_check = check_dist_exists(ctx, package=package, **kwargs)
    if not exists_check.success:
        return exists_check

    # Check for wheel and sdist files
    wheels = list(dist_path.glob("*.whl"))
    sdists = list(dist_path.glob("*.tar.gz"))

    if not wheels and not sdists:
        return Output(
            success=False,
            message="No distribution files found",
            details=[
                {"type": "text", "content": "dist/ directory is empty"},
                {
                    "type": "text",
                    "content": "Expected .whl (wheel) or .tar.gz (sdist) files",
                },
            ],
            next_steps=["Run: relkit build"],
        )

    details: List[Dict[str, Any]] = []
    if wheels:
        details.append(
            {"type": "text", "content": f"Found {len(wheels)} wheel file(s)"}
        )
        for wheel in wheels[:3]:  # Show first 3
            details.append({"type": "text", "content": f"  • {wheel.name}"})

    if sdists:
        details.append(
            {"type": "text", "content": f"Found {len(sdists)} sdist file(s)"}
        )
        for sdist in sdists[:3]:  # Show first 3
            details.append({"type": "text", "content": f"  • {sdist.name}"})

    return Output(
        success=True,
        message=f"Found {len(wheels) + len(sdists)} distribution file(s)",
        details=details,
        data={
            "wheels": [str(w.name) for w in wheels],
            "sdists": [str(s.name) for s in sdists],
            "total": len(wheels) + len(sdists),
        },
    )


def check_dist_version_match(
    ctx: Context, version: Optional[str] = None, package: Optional[str] = None, **kwargs
) -> Output:
    """Check if distribution files match the expected version."""
    # Get dist path with error handling
    try:
        dist_path = ctx.get_dist_path(package)
    except ValueError as e:
        return Output(success=False, message=str(e))

    if version is None:
        if package and ctx.has_workspace:
            try:
                target_pkg = ctx.require_package(package)
                version = target_pkg.version
            except ValueError as e:
                return Output(success=False, message=str(e))
        else:
            version = ctx.version

    # First check if we have dist files
    has_files = check_dist_has_files(ctx, package=package, **kwargs)
    if not has_files.success:
        return has_files

    # Check version in filenames
    wheels = list(dist_path.glob("*.whl"))
    sdists = list(dist_path.glob("*.tar.gz"))

    mismatched = []
    matched = []

    # Version in wheel/sdist filenames is typically name-version-...
    # We need to handle version with - replaced by _
    version_normalized = version.replace("-", "_")

    for dist_file in wheels + sdists:
        filename = dist_file.name
        # Check if version appears in filename
        if version in filename or version_normalized in filename:
            matched.append(filename)
        else:
            # Try to extract version from filename
            # Format is typically: package-version-pyX-none-any.whl
            # or: package-version.tar.gz
            parts = filename.replace(".tar.gz", "").replace(".whl", "").split("-")
            if len(parts) >= 2:
                file_version = parts[1]
                if file_version != version and file_version != version_normalized:
                    mismatched.append(f"{filename} (has version {file_version})")
                else:
                    matched.append(filename)
            else:
                mismatched.append(f"{filename} (cannot determine version)")

    if mismatched:
        return Output(
            success=False,
            message=f"Distribution files don't match version {version}",
            details=[{"type": "text", "content": "Mismatched files:"}]
            + [{"type": "text", "content": f"  • {name}"} for name in mismatched],
            next_steps=[
                "Clean dist: rm -rf dist/",
                "Rebuild: relkit build",
            ],
        )

    return Output(
        success=True,
        message=f"All distribution files match version {version}",
        details=[{"type": "text", "content": f"Verified {len(matched)} file(s)"}],
    )


def check_dist_clean(ctx: Context, package: Optional[str] = None, **kwargs) -> Output:
    """Check if dist directory is clean (no old versions)."""
    # Get dist path with error handling
    try:
        dist_path = ctx.get_dist_path(package)
    except ValueError as e:
        return Output(success=False, message=str(e))

    # First check if dist exists
    exists_check = check_dist_exists(ctx, package=package, **kwargs)
    if not exists_check.success:
        # No dist means it's clean
        return Output(success=True, message="No dist directory (clean)")

    # Get all files
    all_files = list(dist_path.glob("*.whl")) + list(dist_path.glob("*.tar.gz"))

    if not all_files:
        return Output(success=True, message="dist directory is empty (clean)")

    # Group files by detected version
    versions = set()
    for dist_file in all_files:
        filename = dist_file.name
        # Try to extract version
        parts = filename.replace(".tar.gz", "").replace(".whl", "").split("-")
        if len(parts) >= 2:
            versions.add(parts[1])

    if len(versions) > 1:
        return Output(
            success=False,
            message=f"dist contains {len(versions)} different versions",
            details=[{"type": "text", "content": "Found versions:"}]
            + [{"type": "text", "content": f"  • {v}"} for v in sorted(versions)]
            + [
                {"type": "spacer"},
                {"type": "text", "content": "Clean dist before building new version"},
            ],
            next_steps=[
                "Clean dist: rm -rf dist/",
                "Then build: relkit build",
            ],
        )

    return Output(
        success=True,
        message="dist directory is clean (single version)",
        data={"version": list(versions)[0] if versions else None},
    )


def check_build_token_valid(
    ctx: Context, package: Optional[str] = None, **kwargs
) -> Output:
    """
    Check that BUILD_PUBLISH token matches current dist/ contents.

    This ensures we're publishing exactly what was built and reviewed,
    preventing accidental publishing of modified or wrong files.
    """
    # Get the token from environment
    token = os.getenv("BUILD_PUBLISH")
    if not token:
        return Output(
            success=False,
            message="Build token required for publishing",
            details=[
                {"type": "text", "content": "Publishing requires a build token"},
                {"type": "text", "content": "This ensures you publish what you built"},
                {"type": "spacer"},
                {
                    "type": "text",
                    "content": "Build tokens are generated when you run 'relkit build'",
                },
                {"type": "text", "content": "They're valid for 30 minutes"},
            ],
            next_steps=[
                "Build the package: relkit build",
                "Use the BUILD_PUBLISH token it provides",
            ],
        )

    # Get target package to find dist directory
    try:
        if package and ctx.has_workspace:
            target_pkg = ctx.require_package(package)
        else:
            target_pkg = ctx.get_package()
            if not target_pkg:
                # Fallback for simple projects
                from types import SimpleNamespace

                target_pkg = SimpleNamespace(
                    name=ctx.name, version=ctx.version, dist_path=ctx.root / "dist"
                )
    except ValueError as e:
        return Output(success=False, message=str(e))

    dist_path = (
        target_pkg.dist_path
        if hasattr(target_pkg, "dist_path")
        else target_pkg.path / "dist"
    )

    if not dist_path.exists():
        return Output(
            success=False,
            message="No dist/ directory found",
            details=[
                {"type": "text", "content": "Token exists but no dist/ directory"},
                {"type": "text", "content": "The built files may have been deleted"},
            ],
            next_steps=["Rebuild: relkit build"],
        )

    # Calculate current dist state (same way build.py does)
    dist_contents = ""
    for f in sorted(dist_path.glob("*")):
        if f.is_file() and (f.suffix in [".whl", ".gz"]):
            stat = f.stat()
            dist_contents += f"{f.name}:{stat.st_size}:{stat.st_mtime_ns}\n"

    if not dist_contents:
        return Output(
            success=False,
            message="No distribution files found",
            details=[
                {
                    "type": "text",
                    "content": "dist/ exists but contains no .whl or .tar.gz files",
                },
            ],
            next_steps=["Build the package: relkit build"],
        )

    # Verify token matches current state
    if not verify_content_token(target_pkg.name, "build_publish", dist_contents, token):
        return Output(
            success=False,
            message="Build token invalid - dist/ contents changed",
            details=[
                {
                    "type": "text",
                    "content": "The files in dist/ don't match what was built",
                },
                {
                    "type": "text",
                    "content": "Either files were modified, added, or removed",
                },
                {"type": "text", "content": "Or the token has expired (30 minute TTL)"},
                {"type": "spacer"},
                {
                    "type": "text",
                    "content": "This prevents accidentally publishing wrong files",
                },
            ],
            next_steps=[
                "Rebuild to get a new token: relkit build",
                "Use the new BUILD_PUBLISH token",
            ],
        )

    return Output(
        success=True,
        message="Build token valid - files match what was built",
    )
