"""Constants for relkit output and display."""

import os

# Check if NO_EMOJI environment variable is set
NO_EMOJI = os.getenv("NO_EMOJI", "").lower() in ("1", "true", "yes")

# Core status symbols
CHECK_MARK = "SUCCESS:" if NO_EMOJI else "✓"
CROSS_MARK = "ERROR:" if NO_EMOJI else "✗"
WARNING_SIGN = "WARNING:" if NO_EMOJI else "⚠"
INFO_MARK = "INFO:" if NO_EMOJI else "ℹ"

# Navigation and structure symbols
ARROW = "->" if NO_EMOJI else "→"
BULLET = "*" if NO_EMOJI else "•"
