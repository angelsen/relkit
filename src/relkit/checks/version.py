"""Version validation checks."""

from typing import Optional
from ..models import Output, Context
from ..utils import run_git, parse_version


def check_version_format(
    ctx: Context, version: Optional[str] = None, **kwargs
) -> Output:
    """Check if version follows semantic versioning format."""
    if version is None:
        version = ctx.version

    try:
        major, minor, patch = parse_version(version)
        return Output(
            success=True,
            message=f"Version {version} is valid semver",
            data={"major": major, "minor": minor, "patch": patch},
        )
    except ValueError as e:
        return Output(
            success=False,
            message=str(e),
            details=[
                {"type": "text", "content": "Version must follow semantic versioning"},
                {"type": "text", "content": "Format: MAJOR.MINOR.PATCH (e.g., 1.2.3)"},
            ],
            next_steps=["Fix version in pyproject.toml to match X.Y.Z format"],
        )


def check_version_tagged(
    ctx: Context, version: Optional[str] = None, **kwargs
) -> Output:
    """Check if a version is tagged in git."""
    # Get package from kwargs
    package = kwargs.get("package")

    # Get package-specific version and tag
    target_pkg, _, pkg_version, expected_tag = ctx.get_package_context(package)

    if version is None:
        version = pkg_version
    else:
        # If version provided, recalculate expected tag
        if target_pkg and not target_pkg.is_root:
            expected_tag = f"{target_pkg.name}-v{version}"
        else:
            expected_tag = f"v{version}"

    result = run_git(["tag", "-l", expected_tag], cwd=ctx.root)

    if result.returncode != 0:
        return Output(
            success=False,
            message="Failed to check tags",
            details=[{"type": "text", "content": result.stderr.strip()}]
            if result.stderr
            else None,
        )

    if result.stdout.strip():
        return Output(
            success=True,
            message=f"Version {version} is tagged as {expected_tag}",
        )
    else:
        return Output(
            success=False,
            message=f"Version {version} is not tagged",
            details=[
                {"type": "text", "content": f"Expected tag: {expected_tag}"},
                {
                    "type": "text",
                    "content": "Releases should be tagged for traceability",
                },
            ],
            next_steps=[
                "Use: relkit bump <major|minor|patch> to create a tagged release",
            ],
        )


def check_version_not_released(
    ctx: Context, version: Optional[str] = None, package: Optional[str] = None, **kwargs
) -> Output:
    """Check that a version hasn't already been released."""
    # Get the correct context based on package
    if package and ctx.has_workspace:
        try:
            target_pkg = ctx.require_package(package)
            changelog_path = target_pkg.changelog_path
            if version is None:
                version = target_pkg.version
        except ValueError as e:
            return Output(success=False, message=str(e))
    else:
        changelog_path = ctx.root / "CHANGELOG.md"
        if version is None:
            version = ctx.version

    # Check if already tagged
    tag_check = check_version_tagged(ctx, version, package=package, **kwargs)
    if tag_check.success:
        return Output(
            success=False,
            message=f"Version {version} has already been released",
            details=[
                {"type": "text", "content": f"Tag v{version} already exists"},
                {"type": "text", "content": "Cannot release the same version twice"},
            ],
            next_steps=[
                "Bump to a new version: relkit bump <major|minor|patch>",
            ],
        )

    # Check if in changelog (as a released version, not unreleased)
    if changelog_path.exists():
        content = changelog_path.read_text()
        # Look for version with date (indicates released)
        version_with_date_pattern = f"## [{version}] - "
        if version_with_date_pattern in content:
            return Output(
                success=False,
                message=f"Version {version} already in changelog",
                details=[
                    {
                        "type": "text",
                        "content": "Changelog shows this version was already released",
                    },
                    {
                        "type": "text",
                        "content": "Cannot release the same version twice",
                    },
                ],
                next_steps=[
                    "Bump to a new version: relkit bump <major|minor|patch>",
                ],
            )

    return Output(success=True, message=f"Version {version} has not been released")


def check_version_progression(
    ctx: Context,
    old_version: Optional[str] = None,
    new_version: Optional[str] = None,
    bump_type: Optional[str] = None,
    **kwargs,
) -> Output:
    """Check if version bump is logical (no skipping, correct type)."""
    if old_version is None:
        old_version = ctx.version

    if new_version is None and bump_type is None:
        return Output(
            success=False,
            message="Need either new_version or bump_type to check progression",
        )

    try:
        old_major, old_minor, old_patch = parse_version(old_version)

        if new_version:
            new_major, new_minor, new_patch = parse_version(new_version)
        else:
            # Calculate new version from bump_type
            if bump_type == "major":
                new_major, new_minor, new_patch = old_major + 1, 0, 0
            elif bump_type == "minor":
                new_major, new_minor, new_patch = old_major, old_minor + 1, 0
            elif bump_type == "patch":
                new_major, new_minor, new_patch = old_major, old_minor, old_patch + 1
            else:
                return Output(
                    success=False,
                    message=f"Invalid bump type: {bump_type}",
                    details=[
                        {"type": "text", "content": "Valid types: major, minor, patch"}
                    ],
                )
            new_version = f"{new_major}.{new_minor}.{new_patch}"

        # Check if it's actually an increase
        if (new_major, new_minor, new_patch) <= (old_major, old_minor, old_patch):
            return Output(
                success=False,
                message=f"Version {new_version} is not greater than {old_version}",
                details=[
                    {"type": "text", "content": "Versions must increase monotonically"},
                    {"type": "text", "content": "Cannot go backwards or stay the same"},
                ],
            )

        # Determine what kind of bump it is
        if new_major > old_major:
            actual_bump = "major"
            if new_minor != 0 or new_patch != 0:
                return Output(
                    success=False,
                    message="Major bump should reset minor and patch to 0",
                    details=[
                        {"type": "text", "content": f"Expected: {new_major}.0.0"},
                        {"type": "text", "content": f"Got: {new_version}"},
                    ],
                )
        elif new_minor > old_minor:
            actual_bump = "minor"
            if new_patch != 0:
                return Output(
                    success=False,
                    message="Minor bump should reset patch to 0",
                    details=[
                        {
                            "type": "text",
                            "content": f"Expected: {new_major}.{new_minor}.0",
                        },
                        {"type": "text", "content": f"Got: {new_version}"},
                    ],
                )
        elif new_patch > old_patch:
            actual_bump = "patch"
        else:
            return Output(
                success=False,
                message=f"Invalid version progression from {old_version} to {new_version}",
            )

        return Output(
            success=True,
            message=f"Valid {actual_bump} bump: {old_version} → {new_version}",
            data={
                "old_version": old_version,
                "new_version": new_version,
                "bump_type": actual_bump,
            },
        )

    except ValueError as e:
        return Output(
            success=False,
            message=str(e),
        )


def check_version_alignment(
    ctx: Context, package: Optional[str] = None, **kwargs
) -> Output:
    """Check if version is aligned across pyproject.toml, changelog, and git tags."""
    # Get the correct context based on package
    if package and ctx.has_workspace:
        try:
            target_pkg = ctx.require_package(package)
            changelog_path = target_pkg.changelog_path
            version = target_pkg.version
        except ValueError as e:
            return Output(success=False, message=str(e))
    else:
        changelog_path = ctx.root / "CHANGELOG.md"
        version = ctx.version

    issues = []

    # Check if version is in changelog
    if changelog_path.exists():
        content = changelog_path.read_text()
        version_pattern = f"[{version}]"
        if version_pattern not in content:
            issues.append("Version not in CHANGELOG.md")
    else:
        issues.append("No CHANGELOG.md found")

    # Check if version is tagged
    tag_check = check_version_tagged(ctx, version, package=package, **kwargs)
    if not tag_check.success:
        issues.append("Version not tagged in git")

    if issues:
        return Output(
            success=False,
            message=f"Version {version} alignment issues",
            details=[{"type": "text", "content": issue} for issue in issues],
            next_steps=[
                "Use: relkit bump <major|minor|patch> for aligned release",
            ],
        )

    return Output(
        success=True,
        message=f"Version {version} is aligned across all systems",
    )
