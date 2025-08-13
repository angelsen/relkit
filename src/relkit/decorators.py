"""Command decorator for mini-Typer pattern."""

from functools import wraps
from typing import Callable, Any, Dict
from .models import Output, Context


# Global registry of commands
COMMANDS: Dict[str, Dict[str, Any]] = {}


def command(
    name: str,
    help_text: str,
    requires_package: bool = False,
    accepts_any_args: bool = False,
):
    """
    Decorator for CLI commands that handles validation and registration.

    Args:
        name: Command name for CLI
        help_text: Help text to display
        requires_package: Whether command requires package context
        accepts_any_args: Whether command accepts arbitrary arguments (for wrappers)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(ctx: Context, *args, **kwargs) -> Output:
            # Validate workspace requirements
            if requires_package and not ctx.is_workspace:
                return Output(
                    success=False,
                    message=f"Command '{name}' requires a workspace",
                    details=[
                        {
                            "type": "text",
                            "content": "This project is not configured as a workspace",
                        }
                    ],
                    next_steps=["Add [tool.uv.workspace] to pyproject.toml"],
                )

            # Run the actual command
            try:
                return func(ctx, *args, **kwargs)
            except Exception as e:
                return Output(
                    success=False,
                    message=f"Command '{name}' failed: {str(e)}",
                    details=[
                        {"type": "text", "content": f"Error type: {type(e).__name__}"}
                    ],
                )

        # Register command metadata
        # Store wrapper which includes all decorators applied to func
        COMMANDS[name] = {
            "func": wrapper,
            "help": help_text,
            "requires_package": requires_package,
            "accepts_any_args": accepts_any_args,
        }

        # Return wrapper to maintain decorator chain
        return wrapper

    return decorator
