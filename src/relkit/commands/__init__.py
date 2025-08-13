"""Command modules for relkit."""

# Import all commands to register them via side effects
from . import bump  # noqa: F401
from . import build  # noqa: F401
from . import changelog  # noqa: F401
from . import check  # noqa: F401
from . import git  # noqa: F401
from . import init_hooks  # noqa: F401
from . import preflight  # noqa: F401
from . import publish  # noqa: F401
from . import release  # noqa: F401
from . import status  # noqa: F401
from . import test  # noqa: F401
from . import version  # noqa: F401
