"""Bump-specific validation checks."""

from ..models import Output, Context


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