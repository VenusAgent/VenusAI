import abc
from typing import Generic

from attrobj import Object

from .types import Agent, Deps, ReturnType

VenusCode = Agent  # Alias for Agent, used in decorators


class BaseWrapper(abc.ABC):
    """
    Base wrapper class for decorators.
    """

    pass


class ToolFunc(BaseWrapper, Generic[ReturnType]):
    """
    This is used to mark the function as a tool.
    """

    tool: bool
    iscoro: bool
    context_tool: bool


class MCPTool(BaseWrapper, Generic[ReturnType]):
    """
    Wrapper for mcp_tool decorator.
    This is used to mark the function as an MCP tool.
    """

    deps: Deps
    iscoro: bool
    mcp_tool: bool


class SafeFunction(ToolFunc, Generic[ReturnType]):
    """
    Wrapper for safe_call decorator.
    This is used to mark the function as a safe call.
    """

    mcp_tool: bool
    safe_call: bool


class Autofix(ToolFunc, Generic[ReturnType]):
    """
    Wrapper for autofix decorator.
    This is used to mark the function as an autofix.
    """

    autofix: bool
    fix_agent: VenusCode
    autofix_options: Object
