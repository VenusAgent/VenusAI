from typing import Callable, Union

from attrobj import Object

from .types import Agent, Deps, ReturnType

VenusCode = Agent  # Alias for Agent, used in decorators


class BaseWrapper:
    """
    Base wrapper class for decorators.
    """

    pass


class ToolWrapper(BaseWrapper):
    """
    Wrapper for tool decorator.
    This is used to mark the function as a tool.
    """

    tool: bool
    iscoro: bool
    context_tool: bool


class SafeCallWrapper(ToolWrapper):
    """
    Wrapper for safe_call decorator.
    This is used to mark the function as a safe call.
    """

    mcp_tool: bool
    safe_call: bool


class AutofixWrapper(ToolWrapper):
    """
    Wrapper for autofix decorator.
    This is used to mark the function as an autofix.
    """

    autofix: bool
    fix_agent: VenusCode
    autofix_options: Object


class MCPToolWrapper(BaseWrapper):
    """
    Wrapper for mcp_tool decorator.
    This is used to mark the function as an MCP tool.
    """

    deps: Deps
    iscoro: bool
    mcp_tool: bool


ToolFunc = Union[ToolWrapper, Callable[..., ReturnType]]
Autofix = Union[AutofixWrapper, Callable[..., ReturnType]]
MCPTool = Union[MCPToolWrapper, Callable[..., ReturnType]]
SafeFunction = Union[SafeCallWrapper, Callable[..., ReturnType]]
