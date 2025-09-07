"""
Venus AI Agent: An intelligent agent offering advanced functionality for superior results

Docs: https://venus.tomris.dev/docs
"""

from .agent import Tool, Venus, VenusCode
from .decorators import autofix, mcp_tool, safe_call, tool
from .errors import ErrorDict
from .helpers import e2b, tools

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
]

__version__ = "1.28.8"
