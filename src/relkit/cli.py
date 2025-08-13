"""CLI display logic for relkit."""

import sys
from .models import Output
from .constants import SUCCESS_PREFIX, FAILURE_PREFIX


class CLI:
    """Handles display of Output objects and CLI interaction."""

    def display(self, output: Output) -> None:
        """Display an Output object in a user-friendly format."""
        # Main message with status indicator
        if output.success:
            print(f"{SUCCESS_PREFIX}{output.message}")
        else:
            print(f"{FAILURE_PREFIX}{output.message}")

        # Details section
        if output.details:
            print()
            for detail in output.details:
                detail_type = detail.get("type", "text")

                if detail_type == "check":
                    icon = (
                        SUCCESS_PREFIX.strip()
                        if detail.get("success")
                        else FAILURE_PREFIX.strip()
                    )
                    name = detail.get("name", "")
                    message = detail.get("message", "")
                    print(f"  {icon} {name}: {message}")
                    # Handle sub-details for checks
                    if detail.get("sub_details"):
                        for sub_detail in detail["sub_details"]:
                            print(f"    {sub_detail}")
                        if detail.get("overflow", 0) > 0:
                            print(f"    ... and {detail['overflow']} more")
                        print("")  # Empty line between checks
                elif detail_type == "step":
                    icon = (
                        SUCCESS_PREFIX.strip()
                        if detail.get("success")
                        else FAILURE_PREFIX.strip()
                    )
                    name = detail.get("name", "")
                    print(f"  {icon} {name}")
                elif detail_type == "token":
                    icon = (
                        SUCCESS_PREFIX.strip()
                        if detail.get("success")
                        else FAILURE_PREFIX.strip()
                    )
                    message = detail.get("message", "")
                    print(f"  {icon} {message}")
                elif detail_type == "fix":
                    icon = (
                        SUCCESS_PREFIX.strip()
                        if detail.get("success")
                        else FAILURE_PREFIX.strip()
                    )
                    message = detail.get("message", "")
                    print(f"  {icon} {message}")
                elif detail_type == "version_change":
                    from .constants import ARROW

                    old_ver = detail.get("old", "")
                    new_ver = detail.get("new", "")
                    print(f"  Version: {old_ver} {ARROW} {new_ver}")
                elif detail_type == "hook_installed":
                    icon = SUCCESS_PREFIX.strip()
                    name = detail.get("name", "")
                    desc = detail.get("description", "")
                    print(f"  {icon} {name} hook: {desc}")
                elif detail_type == "warning":
                    from .constants import WARNING_PREFIX

                    message = detail.get("message", "")
                    print(f"  {WARNING_PREFIX.strip()} {message}")
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
