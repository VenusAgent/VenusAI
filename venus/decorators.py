"""
Decorators for tool functions.
"""

import inspect
import sys
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from ._decorator_utils import (
    dep_name,
    fix,
    fix_sync,
    get_frame,
    get_frame_info,
    has_deps_param,
    is_context_tool,
    is_factory,
    process_deps,
    safe_run,
)
from .errors import ErrorDict
from .logger import VenusConsole
from .mock_types import Autofix, MCPTool, SafeFunction, ToolFunc
from .types import Deps, Object, ReturnType, _EnableFeature

vc = VenusConsole()


def safe_call(func: Callable[..., ReturnType]) -> SafeFunction[ReturnType]:
    """
    Decorator to suppress exceptions in a function.

    Support for both synchronous and asynchronous functions.
    Use this decorator to make functions safe to call without raising exceptions.

    Args:
        func (Callable[..., ReturnType]): The function to decorate.

    Returns:
        SafeFunction: The decorated function.
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        args = tuple(process_deps(args, func))
        try:
            vc.log(f"Running `{func.__name__}` function safely")
            return await func(*args, **kwargs)
        except Exception:
            _, exc_value, traceback = sys.exc_info()
            frame = get_frame(traceback, exc_value)
            pretty_exc = repr(exc_value.with_traceback(traceback))
            error_data = ErrorDict(
                exception=pretty_exc,
                function=frame.f_code.co_name,
                frame_info=get_frame_info(frame),
                call_stack=[args, kwargs],
            )
            handlers = cast(
                dict[str, dict[str, Callable[..., Optional[Any]]]],
                getattr(func, "handlers", {}),
            )
            if handlers:
                vc.log(
                    f"Function {func.__name__} have handlers, calling them...",
                    bold=True,
                )
                for name, handler in handlers["errors"].items():
                    vc.log(
                        f"Calling `{name}` handler for `{func.__name__}` function ...",
                        bold=True,
                    )
                    result = None
                    maybe_coro = handler(error_data)
                    if inspect.isawaitable(maybe_coro):
                        result = await maybe_coro
                    else:
                        result = maybe_coro

                    if result is not None:
                        vc.log(
                            f"Handler `{name}` returned a result, skipping fix.",
                            bold=True,
                        )
                        return result
            return await fix(func=func, error_data=error_data, args=args, kwargs=kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        args = tuple(process_deps(args, func))
        try:
            vc.log(f"Running `{func.__name__}` function safely")
            return func(*args, **kwargs)
        except Exception:
            _, exc_value, traceback = sys.exc_info()
            frame = get_frame(traceback, exc_value)
            pretty_exc = repr(exc_value.with_traceback(traceback))
            error_data = ErrorDict(
                exception=pretty_exc,
                function=frame.f_code.co_name,
                frame_info=get_frame_info(frame),
                call_stack=[args, kwargs],
            )
            handlers = getattr(func, "handlers", {})
            if handlers:
                vc.log(
                    f"Function {func.__name__} has handlers, calling them...",
                    color="orange1",
                    level_color="orange1",
                    bold=True,
                )
                result = None
                for name, handler in handlers["errors"].items():
                    vc.log(
                        f"Calling handler {name} for function {func.__name__}...",
                        color="orange1",
                        level_color="orange1",
                        bold=True,
                    )
                    result = safe_run(handler, error_data)
                    if result is not None:
                        vc.log(
                            f"Handler `{name}` returned a result{', skipping fix.' if hasattr(func, 'autofix') else '.'}",
                            bold=True,
                        )
                        return result
            return fix_sync(func=func, error_data=error_data, args=args, kwargs=kwargs)

    iscoro = inspect.iscoroutinefunction(func)
    wrapper = async_wrapper if iscoro else sync_wrapper
    if not hasattr(func, "mcp_tool"):
        wrapper.tool = _EnableFeature
        wrapper.context_tool = is_context_tool(func)
    else:
        wrapper.mcp_tool = _EnableFeature
    wrapper.safe_call = _EnableFeature
    wrapper.iscoro = iscoro
    return wrapper


def tool(func: Callable[..., ReturnType]) -> ToolFunc[ReturnType]:
    """
    Decorator to mark a function as a tool.

    Support for both synchronous and asynchronous functions.
    This decorator can be used to register a function as a tool in the agent.

    Args:
        func (Callable[..., ReturnType]): The function to decorate.

    Returns:
        Callable: The decorated function.
    """
    func.tool = _EnableFeature
    func.iscoro = inspect.iscoroutinefunction(func)
    func.context_tool = is_context_tool(func)
    return func


def autofix(
    func: Callable[..., ReturnType] | None = None, *, reload_function: bool = True
) -> Autofix[ReturnType]:
    """
    Decorator to automatically fix the function.

    This decorator can be used to automatically fix the function by
    wrapping it in a safe_call decorator.

    Example usage:
    ```
    @autofix
    def my_function(context: RunContext, a: int, b: int = 0):
        # raises ZeroDivisionError
        return a / b

    @autofix(reload_function=True)
    def my_function(context: RunContext, a: int, b: int = 0):
        # raises ZeroDivisionError
        return a / b
    ```

    Args:
        func (Callable[..., ReturnType]): The function to decorate.
        reload_function (bool): Whether to reload the function after fixing.

    Returns:
        Callable: The decorated function.
    """

    def decorator(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
        func.autofix = _EnableFeature
        func.autofix_options = Object(reload_function=reload_function)
        return func

    if func is not None:
        func.autofix = _EnableFeature
        func.autofix_options = Object(reload_function=reload_function)
        return func

    return decorator


def mcp_tool(
    func: Callable[..., ReturnType] | None = None,
    deps: List | Tuple | Deps | Dict | None = None,
    safe: bool = False,
) -> MCPTool[ReturnType]:
    """
    Decorator to mark a function as an MCP tool.
    This decorator can be used to register a function as a tool in the MCP server.
    Args:
        func (Callable[..., ReturnType] | None): The function to decorate.
        deps (List | Tuple | Deps | Dict | None): Dependencies for the tool.
        safe (bool): Whether to wrap the function in a safe_call decorator.

    Returns:
        Callable: The decorated function.
    """

    def decorator(fn: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
        if safe:
            fn.mcp_tool = _EnableFeature
            fn = safe_call(fn)
        else:
            fn.mcp_tool = _EnableFeature
            fn.iscoro = inspect.iscoroutinefunction(fn)

        if not has_deps_param(fn, Deps):
            if deps:
                raise TypeError(
                    "Function must have a 'deps' parameter of type Deps when deps are provided."
                )
            return fn

        if deps is None:
            tooldeps = Deps()
        elif isinstance(deps, (list, tuple)):
            assert all(
                map(is_factory, deps)
            ), "All dependencies must be factory functions"
            tooldeps = Deps({dep_name(dep): safe_run(dep) for dep in deps})
            tooldeps.update({type(dep): dep for dep in tooldeps.values()})
        elif isinstance(deps, (dict, Deps)):
            assert all(
                map(is_factory, deps.values())
            ), "All dependencies must be factory functions"
            tooldeps = Deps({k: safe_run(v) for k, v in deps.items()})
            tooldeps.update({type(dep): dep for dep in tooldeps.values()})
        else:
            raise TypeError("Invalid type for deps. Must be dictionary or None.")

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            kwargs["deps"] = tooldeps
            return fn(*args, **kwargs)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            kwargs["deps"] = tooldeps
            return await fn(*args, **kwargs)

        wrapper = async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper
        wrapper.deps = tooldeps
        wrapper.mcp_tool = _EnableFeature
        wrapper.iscoro = inspect.iscoroutinefunction(fn)

        return wrapper

    return decorator if func is None else decorator(func)
