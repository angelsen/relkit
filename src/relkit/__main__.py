"""Entry point for relkit CLI."""

import sys
import argparse
from .cli import CLI
from .models import Context
from .decorators import COMMANDS

# Import commands to register them
from .commands import version  # noqa: F401
from .commands import changelog  # noqa: F401
from .commands import bump  # noqa: F401
from .commands import check  # noqa: F401
from .commands import preflight  # noqa: F401
from .commands import status  # noqa: F401
from .commands import build  # noqa: F401
from .commands import test  # noqa: F401
from .commands import publish  # noqa: F401
from .commands import release  # noqa: F401
from .commands import git  # noqa: F401
from .commands import init_hooks  # noqa: F401


def main():
    """Main CLI entry point."""
    cli = CLI()

    # Create argument parser
    parser = argparse.ArgumentParser(
        prog="relkit",
        description="Opinionated release toolkit for modern Python projects",
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register all decorated commands
    for cmd_name, cmd_info in COMMANDS.items():
        subparser = subparsers.add_parser(cmd_name, help=cmd_info["help"])

        # Add bump-specific arguments
        if cmd_name == "bump":
            subparser.add_argument(
                "bump_type",
                nargs="?",
                default="patch",
                choices=["major", "minor", "patch"],
                help="Version bump type (default: patch)",
            )
            subparser.add_argument(
                "--package",
                "-p",
                help="Package to bump (required for workspaces)",
            )

        # Add package argument for commands that support it
        if cmd_name in [
            "status",
            "build",
            "publish",
            "release",
            "version",
            "init-changelog",
        ]:
            subparser.add_argument(
                "--package",
                "-p",
                help="Package to operate on (required for workspaces)",
            )

        # Add check-specific argument
        if cmd_name == "check":
            subparser.add_argument(
                "check_type",
                nargs="?",
                default="all",
                choices=["all", "git", "changelog", "format", "lint", "types"],
                help="Type of check to run (default: all)",
            )
            subparser.add_argument(
                "--fix",
                action="store_true",
                help="Automatically fix issues where possible",
            )

        # Add variadic args for wrapper commands
        if cmd_info.get("accepts_any_args"):
            subparser.add_argument(
                "args",
                nargs=argparse.REMAINDER,  # Captures everything including flags
                help="Arguments to pass through",
            )

        if cmd_info.get("requires_package"):
            subparser.add_argument(
                "--package", "-p", help="Specific package to operate on"
            )

    # Parse arguments
    args = parser.parse_args()

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Load context
    try:
        ctx = Context.from_path()
    except FileNotFoundError:
        cli.error("No pyproject.toml found in current directory or parent")
        return  # For type checker
    except Exception as e:
        cli.error(f"Failed to load project context: {e}")
        return  # For type checker

    # Get command function
    if args.command not in COMMANDS:
        cli.error(f"Unknown command: {args.command}")
        return  # For type checker

    cmd_info = COMMANDS[args.command]
    cmd_func = cmd_info["func"]

    # Prepare kwargs for command
    kwargs = {}
    if hasattr(args, "package") and args.package:
        kwargs["package"] = args.package
    if hasattr(args, "bump_type"):
        kwargs["bump_type"] = args.bump_type
        # Pass package for bump command
        if hasattr(args, "package"):
            kwargs["package"] = args.package
    if hasattr(args, "check_type"):
        kwargs["check_type"] = args.check_type
    if hasattr(args, "fix"):
        kwargs["fix"] = args.fix

    # Execute command
    try:
        # For wrapper commands, pass through args as positional
        if cmd_info.get("accepts_any_args") and hasattr(args, "args"):
            result = cmd_func(ctx, *args.args, **kwargs)
        else:
            # Execute command normally
            result = cmd_func(ctx, **kwargs)

        cli.display(result)
    except Exception as e:
        cli.error(f"Command failed: {e}")


if __name__ == "__main__":
    main()
