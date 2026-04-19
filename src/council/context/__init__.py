# Backward-compatibility shim — import from canonical location instead.
from council.infrastructure.context.builder import ContextBuilder
from council.infrastructure.context.cache import ContextBuildResult

__all__ = ["ContextBuildResult", "ContextBuilder"]
