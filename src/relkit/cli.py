"""CLI display logic for relkit."""

import sys
from .models import Output
from .constants import (
    CHECK_MARK,
    CROSS_MARK,
    ARROW,
    WARNING_SIGN,
    INFO_MARK,
)


class CLI:
    """Handles display of Output objects and CLI interaction."""

    def display_wrapper(self, output: Output) -> None:
        """Display for wrapper commands (git, etc) - minimal interference.

        Principles:
        - stdout is untouched (wrapped tool already wrote to it)
        - stderr gets minimal additions (only our interventions)
        - Success = silent except for details/next_steps guidance
        """
        # Show error message if command failed
        if not output.success and output.message:
            print(f"relkit: {output.message}", file=sys.stderr)

        # Show details with appropriate formatting
        if output.details:
            for detail in output.details:
                detail_type = detail.get("type", "text")
                content = detail.get("content", "")

                if detail_type == "success":
                    print(f"  {CHECK_MARK} {content}", file=sys.stderr)
                elif detail_type == "error":
                    print(f"  {CROSS_MARK} {content}", file=sys.stderr)
                elif detail_type == "warning":
                    print(f"  {WARNING_SIGN} {content}", file=sys.stderr)
                elif detail_type == "info":
                    print(f"  {INFO_MARK} {content}", file=sys.stderr)
                else:  # text or unknown
                    print(f"  {content}", file=sys.stderr)

        # Show next steps with arrows
        if output.next_steps:
            if output.details:  # Add blank line if we had details
                print("", file=sys.stderr)
            for step in output.next_steps:
                print(f"  {ARROW} {step}", file=sys.stderr)

        if not output.success:
            sys.exit(1)

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
                content = detail.get("content", "")

                # Standard detail types (same as display_wrapper)
                if detail_type == "success":
                    print(f"  {CHECK_MARK} {content}")
                elif detail_type == "error":
                    print(f"  {CROSS_MARK} {content}")
                elif detail_type == "warning":
                    print(f"  {WARNING_SIGN} {content}")
                elif detail_type == "info":
                    print(f"  {INFO_MARK} {content}")
                # Special types for native commands
                elif detail_type == "check":
                    # For checks, show pass/fail clearly but minimally
                    status = CHECK_MARK if detail.get("success") else CROSS_MARK
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
                    status = CHECK_MARK if detail.get("success") else CROSS_MARK
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
                    old_ver = detail.get("old", "")
                    new_ver = detail.get("new", "")
                    print(f"  Version: {old_ver} {ARROW} {new_ver}")
                elif detail_type == "hook_installed":
                    name = detail.get("name", "")
                    desc = detail.get("description", "")
                    print(f"  Installed {name} hook: {desc}")
                elif detail_type == "text":
                    content = detail.get("content", "")
                    print(f"  {content}")
                elif detail_type == "spacer":
                    print()
                else:
                    # Unknown type, try to print content if available
                    content = detail.get("content", str(detail))
                    print(f"  {content}")

        # Next steps section (consistent with display_wrapper)
        if output.next_steps:
            print()  # Blank line before next steps
            for step in output.next_steps:
                print(f"  {ARROW} {step}")

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
