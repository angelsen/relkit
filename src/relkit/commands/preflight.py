"""Preflight checks command."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context
from ..workflows import Workflow
from ..checks.git import check_clean_working_tree
from ..checks.changelog import check_version_entry, check_relkit_compatibility
from ..checks.quality import check_formatting, check_linting, check_types


@command("preflight", "Run pre-release checks")
def preflight(ctx: Context, package: Optional[str] = None) -> Output:
    """Run all pre-release checks using workflow pattern."""
    return (
        Workflow("preflight")
        .check(check_clean_working_tree)
        .check(check_relkit_compatibility)  # Check compatibility first
        .check(check_version_entry)  # Then check version entry
        .parallel(check_formatting, check_linting, check_types)
        .run(ctx, package=package)
    )
