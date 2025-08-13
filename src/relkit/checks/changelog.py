"""Changelog validation checks."""

import os
from typing import Optional
from ..models import Output, Context
from ..utils import run_git
from ..safety import generate_token, verify_token


def check_changelog_exists(ctx: Context, **kwargs) -> Output:
    """Check if CHANGELOG.md exists."""
    # Get package from kwargs
    package = kwargs.get("package")

    # Get changelog path for the package
    _, changelog_path, _, _ = ctx.get_package_context(package)

    if not changelog_path.exists():
        # Build appropriate next step based on package
        next_step = "Run: relkit init-changelog"
        if package:
            next_step = f"Run: relkit init-changelog --package {package}"

        return Output(
            success=False,
            message="No CHANGELOG.md found",
            details=[
                {
                    "type": "text",
                    "content": "This project requires a changelog for releases",
                }
            ],
            next_steps=[next_step],
        )

    return Output(success=True, message="CHANGELOG.md exists")


def check_relkit_compatibility(ctx: Context, **kwargs) -> Output:
    """
    Check if changelog is compatible with relkit's workflow.

    relkit requires an [Unreleased] section for its bump workflow.
    This check ensures the changelog can be managed by relkit.
    """
    # Get package from kwargs
    package = kwargs.get("package")

    # Get changelog path for the package
    _, changelog_path, _, _ = ctx.get_package_context(package)

    if not changelog_path.exists():
        return check_changelog_exists(ctx, **kwargs)

    content = changelog_path.read_text()

    # Check for [Unreleased] section
    if "## [Unreleased]" not in content:
        # Find where user should add it (after header, before first version)
        lines = content.split("\n")
        insert_line = None

        for i, line in enumerate(lines, 1):
            # Look for the first version entry
            if line.startswith("## [") and "[Unreleased]" not in line:
                insert_line = i
                break

        if not insert_line:
            insert_line = "after the header"
        else:
            insert_line = f"before line {insert_line}"

        return Output(
            success=False,
            message="Changelog incompatible with relkit workflow",
            details=[
                {
                    "type": "text",
                    "content": "relkit requires an [Unreleased] section for version management",
                },
                {
                    "type": "text",
                    "content": "Your changelog has version entries but no [Unreleased] section",
                },
                {"type": "spacer"},
                {"type": "text", "content": f"Add this {insert_line}:"},
                {
                    "type": "code",
                    "content": "## [Unreleased]\n\n### Added\n\n### Changed\n\n### Fixed\n\n### Removed\n",
                },
                {"type": "spacer"},
                {
                    "type": "text",
                    "content": "Your existing version entries remain unchanged",
                },
            ],
            next_steps=[
                "Edit CHANGELOG.md manually",
                "Add the [Unreleased] section",
                "Document future changes there until next bump",
            ],
        )

    return Output(success=True, message="Changelog is relkit-compatible")


def check_unreleased_content(ctx: Context, **kwargs) -> Output:
    """Check if [Unreleased] section has meaningful content."""
    # Get package from kwargs
    package = kwargs.get("package")

    # Get changelog path for the package
    _, changelog_path, _, _ = ctx.get_package_context(package)

    if not changelog_path.exists():
        return check_changelog_exists(ctx, **kwargs)

    content = changelog_path.read_text()

    # Find [Unreleased] section
    unreleased_idx = content.find("## [Unreleased]")
    if unreleased_idx == -1:
        return Output(
            success=False,
            message="No [Unreleased] section in changelog",
            next_steps=["Add ## [Unreleased] section to CHANGELOG.md"],
        )

    # Find the next section boundary
    next_section = content.find("\n## [", unreleased_idx + 1)
    if next_section == -1:
        next_section = len(content)

    section_content = content[unreleased_idx:next_section]

    # Parse and check for actual content
    has_content = False

    for line in section_content.split("\n"):
        stripped = line.strip()

        # Skip empty lines, headers, and comments
        if (
            not stripped
            or stripped == "## [Unreleased]"
            or stripped.startswith("###")
            or stripped.startswith("<!--")
            or stripped.endswith("-->")
        ):
            continue

        # Check for actual content (bullet points or text)
        if (
            stripped.startswith("-")
            or stripped.startswith("*")
            or stripped.startswith("+")
            or len(stripped) > 0
        ):
            has_content = True
            break

    if not has_content:
        return Output(
            success=False,
            message="Changelog [Unreleased] section is empty",
            next_steps=[
                "Add entries to CHANGELOG.md under ## [Unreleased]",
                "Document what was added, changed, fixed, or removed",
            ],
        )

    return Output(success=True, message="Changelog has unreleased content")


def check_version_entry(
    ctx: Context, version: Optional[str] = None, **kwargs
) -> Output:
    """Check if a specific version has a changelog entry with content."""
    # Get package from kwargs (could be passed as parameter or in kwargs)
    package = kwargs.get("package")

    # Get changelog path and version for the package
    _, changelog_path, pkg_version, _ = ctx.get_package_context(package)

    if version is None:
        version = pkg_version

    if not changelog_path.exists():
        return check_changelog_exists(ctx, **kwargs)

    content = changelog_path.read_text()
    version_pattern = f"[{version}]"

    # Check if version is in changelog
    if version_pattern not in content:
        return Output(
            success=False,
            message=f"No changelog entry for version {version}",
            details=[
                {
                    "type": "text",
                    "content": "Every release must have a changelog entry",
                },
                {
                    "type": "text",
                    "content": "The changelog documents what changed for users",
                },
            ],
            next_steps=[
                "Add your changes to CHANGELOG.md under [Unreleased]",
                "Then run: relkit bump <major|minor|patch>",
            ],
        )

    # Check that the version section has actual content
    version_idx = content.index(version_pattern)
    next_section_idx = content.find("\n## [", version_idx + 1)
    if next_section_idx == -1:
        next_section_idx = len(content)

    version_content = content[version_idx:next_section_idx].strip()

    # Check for meaningful content
    has_content = False
    for line in version_content.split("\n")[1:]:  # Skip the header line
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("###")
            and not stripped.startswith("<!--")
            and not stripped.endswith("-->")
        ):
            has_content = True
            break

    if not has_content:
        return Output(
            success=False,
            message=f"Changelog entry for {version} is empty",
            details=[
                {
                    "type": "text",
                    "content": "Version section exists but has no content",
                },
                {"type": "text", "content": "Users need to know what changed"},
            ],
            next_steps=[
                "Add meaningful entries to the changelog",
                "Document what was added, changed, fixed, or removed",
            ],
        )

    return Output(success=True, message=f"Changelog has entry for version {version}")


def check_commits_documented(ctx: Context, **kwargs) -> Output:
    """Check if commits since last tag are documented in changelog."""
    # Get package from kwargs
    package = kwargs.get("package")

    # Check for force override token
    token_env = "FORCE_EMPTY_CHANGELOG"
    provided = os.getenv(token_env)

    if provided and verify_token(ctx.name, "force_empty_changelog", provided):
        return Output(success=True, message="Changelog check overridden")

    # Get package-specific commit information
    target_pkg, _, _, _ = ctx.get_package_context(package)

    if target_pkg:
        last_tag = target_pkg.get_last_tag()
        # Count commits since package tag
        if last_tag:
            result = run_git(["rev-list", f"{last_tag}..HEAD", "--count"], cwd=ctx.root)
            commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
        else:
            result = run_git(["rev-list", "HEAD", "--count"], cwd=ctx.root)
            commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
    else:
        # Fallback to context properties
        commit_count = ctx.commits_since_tag
        last_tag = ctx.last_tag

    last_tag = last_tag or "start of project"

    # Case 1: No commits since last tag
    if commit_count == 0:
        new_token = generate_token(ctx.name, "force_empty_changelog", ttl=300)
        return Output(
            success=False,
            message="No commits since last tag - nothing to release",
            details=[
                {"type": "text", "content": f"Last tag: {last_tag}"},
                {
                    "type": "text",
                    "content": "No changes have been made since the last release",
                },
                {"type": "spacer"},
                {
                    "type": "text",
                    "content": "If you need to bump anyway (e.g., rebuild):",
                },
                {"type": "text", "content": "Token expires in 5 minutes"},
            ],
            next_steps=[
                "Make changes before creating a new release",
                f"Or force bump: {token_env}={new_token} relkit bump",
            ],
        )

    # Case 2: Have commits - check changelog
    changelog_result = check_unreleased_content(ctx, **kwargs)

    if not changelog_result.success:
        # Get commit list to show user
        if last_tag:
            result = run_git(
                ["log", f"{last_tag}..HEAD", "--oneline", "--no-merges"], cwd=ctx.root
            )
        else:
            result = run_git(
                ["log", "--oneline", "--no-merges", "-n", "20"], cwd=ctx.root
            )

        commits = []
        if result.returncode == 0 and result.stdout.strip():
            commits = result.stdout.strip().split("\n")

        # Build details showing the commits
        details = [
            {
                "type": "text",
                "content": f"Found {commit_count} commit(s) since {last_tag}",
            },
            {
                "type": "text",
                "content": "But [Unreleased] section in CHANGELOG.md is empty",
            },
            {"type": "spacer"},
            {"type": "text", "content": "Recent commits that need documentation:"},
        ]

        # Show up to 10 commits
        for commit in commits[:10]:
            details.append({"type": "text", "content": f"  {commit}"})

        if len(commits) > 10:
            details.append(
                {"type": "text", "content": f"  ... and {len(commits) - 10} more"}
            )

        details.extend(
            [
                {"type": "spacer"},
                {"type": "text", "content": "Every release must document what changed"},
                {
                    "type": "text",
                    "content": "Add entries under ## [Unreleased] in CHANGELOG.md",
                },
            ]
        )

        # Generate override token for edge cases
        new_token = generate_token(ctx.name, "force_empty_changelog", ttl=300)
        details.append({"type": "spacer"})
        details.append(
            {
                "type": "text",
                "content": "To force bump without changelog (not recommended):",
            }
        )
        details.append(
            {"type": "text", "content": f"{token_env}={new_token} relkit bump"}
        )
        details.append({"type": "text", "content": "Token expires in 5 minutes"})

        return Output(
            success=False,
            message=f"Found {commit_count} commit(s) but changelog is empty",
            details=details,
            next_steps=[
                "Add entries to CHANGELOG.md under ## [Unreleased]",
                "Document what changed in this release",
                f"Or force: {token_env}={new_token} relkit bump",
            ],
        )

    # All good - have commits and changelog
    return Output(success=True, message="Commits and changelog are in sync")


def check_major_bump_justification(
    ctx: Context, bump_type: str = "patch", **kwargs
) -> Output:
    """Check if major bump is justified (warns for breaking changes)."""
    # Get bump_type from kwargs if not passed directly
    if "bump_type" in kwargs:
        bump_type = kwargs["bump_type"]

    if bump_type != "major":
        return Output(success=True, message="Not a major bump")

    return Output(
        success=False,
        message="Major version bump (breaking change)",
        details=[
            {"type": "text", "content": "Major bumps indicate breaking changes"},
            {"type": "text", "content": "Users will need to update their code"},
        ],
    )
