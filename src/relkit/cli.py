"""CLI display logic for relkit."""

import sys
from .models import Output


class CLI:
    """Handles display of Output objects and CLI interaction."""

    def display_wrapper(self, output: Output) -> None:
        """Display for wrapper commands (git, etc) - minimal interference.

        Principles:
        - stdout is untouched (wrapped tool already wrote to it)
        - stderr gets minimal additions (only our interventions)
        - Success = completely silent
        """
        if not output.success:
            # Only show our interventions/blocks to stderr
            if output.message:
                print(f"relkit: {output.message}", file=sys.stderr)

            # Show details if provided (for context)
            if output.details:
                for detail in output.details:
                    if detail.get("type") == "text":
                        content = detail.get("content", "")
                        print(f"  {content}", file=sys.stderr)

            # Show next steps if provided
            if output.next_steps:
                for step in output.next_steps:
                    print(f"  {step}", file=sys.stderr)

            sys.exit(1)
        # Success = silent (wrapped tool's output stands alone)

    def display(self, output: Output) -> None:
        """Display an Output object in a user-friendly format for native commands."""
        # For native commands, be informative but not verbose
        if output.message:
            if output.success:
                # Just print the message, no checkmark prefix
                print(output.message)
            else:
                # Error messages to stderr with minimal prefix
                print(f"Error: {output.message}", file=sys.stderr)

        # Details section
        if output.details:
            for detail in output.details:
                detail_type = detail.get("type", "text")

                if detail_type == "check":
                    # For checks, show pass/fail clearly but minimally
                    status = "✓" if detail.get("success") else "✗"
                    name = detail.get("name", "")
                    message = detail.get("message", "")
                    print(f"  {status} {name}: {message}")
                    # Handle sub-details for checks
                    if detail.get("sub_details"):
                        for sub_detail in detail["sub_details"]:
                            print(f"    {sub_detail}")
                        if detail.get("overflow", 0) > 0:
                            print(f"    ... and {detail['overflow']} more")
                        print("")  # Empty line between checks
                elif detail_type == "step":
                    # For workflow steps, minimal indicators
                    status = "✓" if detail.get("success") else "✗"
                    name = detail.get("name", "")
                    print(f"  {status} {name}")
                elif detail_type == "token":
                    # Tokens are informational, no status needed
                    message = detail.get("message", "")
                    print(f"  {message}")
                elif detail_type == "fix":
                    # Show what was fixed
                    message = detail.get("message", "")
                    print(f"  Fixed: {message}")
                elif detail_type == "version_change":
                    from .constants import ARROW

                    old_ver = detail.get("old", "")
                    new_ver = detail.get("new", "")
                    print(f"  Version: {old_ver} {ARROW} {new_ver}")
                elif detail_type == "hook_installed":
                    name = detail.get("name", "")
                    desc = detail.get("description", "")
                    print(f"  Installed {name} hook: {desc}")
                elif detail_type == "warning":
                    message = detail.get("message", "")
                    print(f"  Warning: {message}")
                elif detail_type == "text":
                    content = detail.get("content", "")
                    print(f"  {content}")
                elif detail_type == "spacer":
                    print()
                else:
                    # Unknown type, try to print content if available
                    content = detail.get("content", str(detail))
                    print(f"  {content}")

        # Next steps section
        if output.next_steps:
            print("\nNext steps:")
            for i, step in enumerate(output.next_steps, 1):
                print(f"  {i}. {step}")

        # Exit with appropriate code
        if not output.success:
            sys.exit(1)

    def error(self, message: str) -> None:
        """Display an error message and exit."""
        print(f"Error: {message}", file=sys.stderr)
        sys.exit(1)

    def info(self, message: str) -> None:
        """Display an informational message."""
        print(message)
