"""Release workflow command."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context
from ..workflows import Workflow
from ..checks.hooks import check_hooks_initialized
from .preflight import preflight
from .build import build
from .test import test
from .publish import publish


@command("release", "Complete release workflow")
def release(ctx: Context, package: Optional[str] = None) -> Output:
    """Run complete release workflow: preflight, build, test, publish.

    Note: This assumes you've already run `relkit bump` to create the release tag.
    The bump command handles version, changelog, commit, and tag atomically.
    """
    # Check hooks are initialized first
    hooks_check = check_hooks_initialized(ctx)
    if not hooks_check.success:
        return hooks_check

    # Create workflow with all steps
    workflow = Workflow("release")

    # Add preflight checks
    workflow.step(preflight)

    # Build the package
    workflow.step(build)

    # Test the built package
    workflow.step(test)

    # Publish if public, skip if private
    if ctx.is_public:
        workflow.step(publish)
    else:
        # Add a step that just reports skipping
        def skip_publish(ctx: Context, **kwargs) -> Output:
            return Output(success=True, message="Skipped publish (private package)")

        workflow.step(skip_publish)

    # Run the workflow
    return workflow.run(ctx, package=package)
