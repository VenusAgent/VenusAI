"""
Module utilities for safely importing and fetching tools from specified modules.
"""

import importlib
from typing import Any, Callable

from .decorators import _EnableFeature
from .errors import InvalidModuleName, ModuleRaisedException


def import_module(
    tool_module: str, mcp_tool: bool = False, load_all: bool = False
) -> list[Callable[..., Any]]:
    """
    Import tool module and fetch tools from them.

    Args:
        tool_module (str): The name of the module to import.
        mcp_tool (bool): Whether to load MCP tools.
        load_all (bool): Whether to load all tools regardless of type.

    Returns:
        list[Callable[..., Any]]: A list of callable tools from the module.

    Raises:
        InvalidModuleName: If the module name is not provided.
        ModuleImportError: If the module cannot be imported.
        ModuleRaisedException: If the module raises an exception during import.
    """
    if not tool_module:
        raise InvalidModuleName("Module name must be provided to integrate tools.")

    try:
        module = importlib.import_module(tool_module)
    except ImportError:
        raise InvalidModuleName(
            f"Failed to import {tool_module!r} module. "
            "Make sure the module name is correct.",
        )
    except Exception as exc:
        raise ModuleRaisedException(
            f"Failed to import {tool_module} module "
            "because module raised an exception."
        ) from exc

    if load_all:
        condition = (
            lambda x: (
                getattr(getattr(module, x), "tool", None)
                or getattr(getattr(module, x), "mcp_tool", None)
            )
            == _EnableFeature
        )
    else:
        attr_name = "mcp_tool" if mcp_tool else "tool"
        condition = (
            lambda x: getattr(getattr(module, x), attr_name, None) == _EnableFeature
        )

    tool_names = [
        name
        for name in dir(module)
        if condition(name) and callable(getattr(module, name))
    ]

    return [getattr(module, attr) for attr in tool_names]


def fetch_module_tools(
    tool_modules: str | list[str], mcp_tool: bool = False, load_all: bool = False
) -> list[Callable[..., Any]]:
    """
    Fetch tools from the specified module(s).

    Args:
        tool_modules (str | list[str]): The module(s) from which to fetch tools.
        mcp_tool (bool): Whether to load MCP tools.
        load_all (bool): Whether to load all tools regardless of type.

    Returns:
        list[Callable[..., Any]]: A list of callable tools from the specified module(s).
    """
    tools = []

    if not tool_modules:
        return []

    if isinstance(tool_modules, str):
        return import_module(tool_modules, mcp_tool=mcp_tool, load_all=load_all)

    if isinstance(tool_modules, (list, tuple, set)):
        for module in tool_modules:
            tools.extend(import_module(module, mcp_tool=mcp_tool, load_all=load_all))
        return tools

    return []
