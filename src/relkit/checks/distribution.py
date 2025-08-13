"""Distribution and build validation checks."""

from typing import Optional, List, Dict, Any
from ..models import Output, Context


def check_dist_exists(ctx: Context, **kwargs) -> Output:
    """Check if dist directory exists."""
    dist_path = ctx.root / "dist"
    
    if not dist_path.exists():
        return Output(
            success=False,
            message="No dist directory found",
            details=[
                {"type": "text", "content": "Build artifacts are stored in dist/"},
                {"type": "text", "content": "This directory is created by the build process"},
            ],
            next_steps=["Run: relkit build"],
        )
    
    if not dist_path.is_dir():
        return Output(
            success=False,
            message="dist exists but is not a directory",
            details=[
                {"type": "text", "content": "dist should be a directory containing build artifacts"},
            ],
            next_steps=[
                "Remove the file: rm dist",
                "Then build: relkit build",
            ],
        )
    
    return Output(success=True, message="dist directory exists")


def check_dist_has_files(ctx: Context, **kwargs) -> Output:
    """Check if dist directory contains distribution files."""
    dist_path = ctx.root / "dist"
    
    # First check if dist exists
    exists_check = check_dist_exists(ctx, **kwargs)
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
                {"type": "text", "content": "Expected .whl (wheel) or .tar.gz (sdist) files"},
            ],
            next_steps=["Run: relkit build"],
        )
    
    details: List[Dict[str, Any]] = []
    if wheels:
        details.append({"type": "text", "content": f"Found {len(wheels)} wheel file(s)"})
        for wheel in wheels[:3]:  # Show first 3
            details.append({"type": "text", "content": f"  • {wheel.name}"})
    
    if sdists:
        details.append({"type": "text", "content": f"Found {len(sdists)} sdist file(s)"})
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


def check_dist_version_match(ctx: Context, version: Optional[str] = None, **kwargs) -> Output:
    """Check if distribution files match the expected version."""
    if version is None:
        version = ctx.version
    
    dist_path = ctx.root / "dist"
    
    # First check if we have dist files
    has_files = check_dist_has_files(ctx, **kwargs)
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
            details=[
                {"type": "text", "content": "Mismatched files:"}
            ] + [
                {"type": "text", "content": f"  • {name}"} for name in mismatched
            ],
            next_steps=[
                "Clean dist: rm -rf dist/",
                "Rebuild: relkit build",
            ],
        )
    
    return Output(
        success=True,
        message=f"All distribution files match version {version}",
        details=[
            {"type": "text", "content": f"Verified {len(matched)} file(s)"}
        ],
    )


def check_dist_clean(ctx: Context, **kwargs) -> Output:
    """Check if dist directory is clean (no old versions)."""
    dist_path = ctx.root / "dist"
    
    # First check if dist exists
    exists_check = check_dist_exists(ctx, **kwargs)
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
            details=[
                {"type": "text", "content": "Found versions:"}
            ] + [
                {"type": "text", "content": f"  • {v}"} for v in sorted(versions)
            ] + [
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