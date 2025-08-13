"""Preflight checks command."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context
from ..workflows import Workflow
from ..checks.git import check_git_clean, check_changelog
from ..checks.quality import check_formatting, check_linting, check_types


@command("preflight", "Run pre-release checks")
def preflight(ctx: Context, package: Optional[str] = None) -> Output:
    """Run all pre-release checks using workflow pattern."""
    return (
        Workflow("preflight")
        .check(check_git_clean)
        .check(check_changelog)
        .parallel(check_formatting, check_linting, check_types)
        .run(ctx, package=package)
    )
