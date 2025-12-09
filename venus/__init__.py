"""
Venus AI Agent: An intelligent agent offering advanced functionality for superior results

Docs: https://venus.tomris.dev/docs
"""

from .agent import StructuredDict, Tool, Venus, VenusCode
from .decorators import autofix, mcp_tool, safe_call, tool
from .errors import ErrorDict
from .helpers import e2b, tools
from .permissions import Permission
from .prompts import CODING_PROMPT, CUSTOM_FIX_PROMPT, FIX_PROMPT
from .types import CacheDeps, Deps, DepsT, ModelRetry, RunContext

__all__ = [
    "Venus",
    "VenusCode",
    "Tool",
    "tool",
    "mcp_tool",
    "safe_call",
    "autofix",
    "ErrorDict",
    "e2b",
    "tools",
    "StructuredDict",
    "RunContext",
    "Deps",
    "DepsT",
    "CacheDeps",
    "ModelRetry",
    "Permission",
    "CODING_PROMPT",
    "CUSTOM_FIX_PROMPT",
    "FIX_PROMPT",
]

__version__ = "1.29.0"
