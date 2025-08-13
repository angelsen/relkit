"""Constants for relkit output and display."""

# Display symbols - can be disabled or changed via environment
import os

# Check if NO_EMOJI environment variable is set
NO_EMOJI = os.getenv("NO_EMOJI", "").lower() in ("1", "true", "yes")

# Success/failure indicators
CHECK_MARK = "" if NO_EMOJI else "✓"
CROSS_MARK = "" if NO_EMOJI else "✗"
WARNING_SIGN = "WARNING:" if NO_EMOJI else "⚠️"

# Other symbols
ARROW = "->" if NO_EMOJI else "→"

# Prefixes for output
SUCCESS_PREFIX = f"{CHECK_MARK} " if CHECK_MARK else "SUCCESS: "
FAILURE_PREFIX = f"{CROSS_MARK} " if CROSS_MARK else "ERROR: "
WARNING_PREFIX = f"{WARNING_SIGN} " if not NO_EMOJI else "WARNING: "
