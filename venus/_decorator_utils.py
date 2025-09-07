"""
Utilities for decorators in the Venus framework.
"""

import importlib.util
import inspect
import os
import re
from asyncio import run
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, ParamSpec, TypeVar, Union, get_type_hints

from venus.mock_types import Autofix

from attrobj import Object
from pydantic_ai import StructuredDict

from .errors import (ContextParamDuplicated, ErrorDict, InvalidContextParam,
                     InvalidDependencyParam, MainBlockNotFound)
from .logger import VenusConsole
from .schemas import FixFuncResult
from .settings import settings
from .types import Deps, ReturnType, RunContext, get_base_type

DepsT = TypeVar("DepsT")
Param = ParamSpec("Param")

vc = VenusConsole()
main_pattern = re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")


# TODO: Clarify fix instructions logic after first release
fix_instructions = """
Address the issue in the identified line without modifying unrelated parts of the file.
Focus on resolving the error precisely without introducing new imports or unrelated changes.
Provide a minimal and accurate fix for the error while preserving the existing code structure.
Verify correctness after applying the fix and ensure no new issues are introduced.
"""


def generate_fix_message(source: str, filepath: str, error_data: ErrorDict) -> str:
    """
    Generate a fix message for the error data.

    Args:
        error_data (ErrorDict): The error data containing details about the error.
        source (str): The source code of the function where the error occurred.
        filepath (str): The file path of the function where the error occurred.

    Returns:
        str: A formatted string with the error details.
    """
    return "\n".join(
        (
            fix_instructions,
            f"An error occurred in the function `{error_data.function}` at file location `{error_data.location}`.",
            "Exception details:",
            f"Type: {error_data.exception}",
            f"Code Context: {error_data.context!r}",
            settings.custom_fix_prompt.format(source=source, filepath=filepath),
        )
    )


def safe_run(fn: Callable[..., ReturnType], *args, **kwargs) -> ReturnType:
    """
    Run a function within correct context, sync/async.

    Args:
        fn (Callable[..., ReturnType]): The function to run.
    Returns:
        ReturnType: The result of the function.
    """
    if inspect.iscoroutinefunction(fn):
        return run(fn(*args, **kwargs))
    return fn(*args, **kwargs)


def makekey(fn: Callable[..., Any]) -> Callable[..., str]:
    """
    Make cache key for a cached function.

    Args:
        fn (Callable): Cached function to make key.

    Returns:
        Callable: The callable that takes function arguments to make key.
    """

    def _makekey(*args, **kwargs) -> str:
        if args or kwargs:
            return f"{fn.__qualname__}:{args}:{kwargs}"
        return fn.__qualname__

    return _makekey


def get_frame_info(frame: Any) -> dict:
    """
    Get the frame information.

    Args:
        frame (Any): The frame object.

    Returns:
        dict: A dictionary containing the frame information.
    """
    if frame is None:
        return {}

    frame_info = inspect.getframeinfo(frame)
    return {
        "lineno": (
            frame_info.lineno if isinstance(frame, TracebackType) else frame.f_lineno
        ),
        "filename": frame_info.filename,
        "caller": frame_info.function,
        "context": frame_info.code_context,
    }


def get_frame(trace: TracebackType, exception: BaseException) -> Any:
    """
    Get the frame from the traceback or exception.

    Defaults to the current frame if no traceback or exception is provided.

    Args:
        trace (TracebackType): The traceback object.
        exception (BaseException): The exception object.

    Returns:
        Any: The frame object.
    """
    if trace and hasattr(trace, "tb_frame") and trace.tb_frame:
        return (trace.tb_next.tb_frame if trace.tb_next else None) or trace.tb_frame
    elif exception and hasattr(exception, "__traceback__") and exception.__traceback__:
        if hasattr(exception.__traceback__, "tb_frame"):
            tb = exception.__traceback__
            return (tb.tb_next.tb_frame if tb.tb_next else None) or tb.tb_frame
    return inspect.currentframe()


def is_context_tool(func: Callable[..., ReturnType]) -> bool:
    """
    Check if the function is a context tool.

    A context tool is a function that takes RunContext as its first parameter.

    Args:
        func (Callable[..., ReturnType]): The function to check.
        any (bool): Whether to allow any context parameter.

    Returns:
        bool: True if the function is a context tool, False otherwise.
    """
    params = iter(inspect.signature(func).parameters)
    head_param = next(params, None)
    context_params = [
        get_type_hints(func).get(p, None)
        for p in params
        if (get_base_type(func, p)) is RunContext
    ]
    if head_param is None:
        return False
    head_param_type = get_base_type(func, head_param)
    if context_params:
        raise ContextParamDuplicated(
            f"Function {func.__name__!r} has {len(context_params) + bool(head_param_type is RunContext)} context parameters "
            f"but expected one RunContext parameter as the first parameter."
        )
    if head_param_type is not RunContext and context_params:
        raise InvalidContextParam(
            f"Function {func.__name__!r} is expected to have RunContext as the first "
            f"parameter but context param found in wrong location."
        )
    return head_param_type is RunContext


async def fix(
    func: Autofix,
    error_data: ErrorDict,
    args: tuple = (),
    kwargs: dict = {},
) -> Union[ErrorDict, ReturnType]:
    """
    Fix function to be used in the safe_call decorator for asynchronous functions.

    This function is called when an exception occurs in the decorated function.
    It returns a FixFuncResult object with the error data.

    Returns:
        FixFuncResult: The result of the fix function.
    """
    source = inspect.getsource(func)
    filepath = inspect.getfile(func)

    if hasattr(func, "autofix") and func.autofix:
        if not hasattr(func, "fix_agent") or not hasattr(func.fix_agent, "run"):
            vc.fail(
                f"Error detected in function {func.__name__!r} but you have to wrap function with @agent.safe or @agent.safe_plain decorator to use autofix feature."
            )
            return error_data
        elif not hasattr(func.fix_agent, "run") or not func.fix_agent:
            vc.fail(
                f"Error detected in function {func.__name__!r} but you have to call set_fix_agent with your fix agent instance to use autofix feature."
            )
            return error_data

        vc.info(f"Autofixing error in function {func.__name__!r}...")
        vc.fail(f"Error detected in function:[bold yellow]{func.__name__!r}[/]")

        settings.custom_fix_prompt.format(
            source=source,
            filepath=filepath,
        )

        fix_result = await func.fix_agent.run(
            user_prompt=generate_fix_message(
                source=source,
                filepath=filepath,
                error_data=error_data,
            ),
            output_type=FixFuncResult,
        )

        fix_time = datetime.now()

        fix_data = {
            "filepath": filepath,
            "source": source,
            "function": func.__name__,
            "result": fix_result.output.model_dump(),
            "fixdate": {
                "iso": fix_time.isoformat(),
                "unix": int(fix_time.timestamp()),
            },
        }

        func.fix_agent.fixdb.insert(fix_data)

        vc.log("Fix process ended successfully!")

        if func.autofix_options.reload_function:
            module_path = os.path.abspath(inspect.getfile(func))
            content = Path(module_path).read_text(encoding="utf-8")

            if not main_pattern.search(content):
                raise MainBlockNotFound(
                    f"Main block (`if __name__ == '__main__':`) not found in the file {module_path!r}. "
                    "When using reload_function=True, you must place function calls inside this main block. "
                    "Please ensure the file includes a proper main guard to avoid runtime issues."
                )

            module_name = os.path.splitext(os.path.basename(module_path))[0]
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.import_module(spec.name)

            updated_func = getattr(module, func.__name__, None)
            if updated_func is None:
                vc.log(
                    f"Function {func.__name__!r} not found in module {module_name!r}.",
                    bold=True,
                    color="red",
                )
                return error_data
            vc.log(f"Function {func.__name__!r} reloaded successfully!")
            result = await updated_func(*args, **kwargs)
            return result
    return error_data


def fix_sync(
    func: Autofix,
    error_data: ErrorDict,
    args: tuple = (),
    kwargs: dict = {},
) -> Union[ErrorDict, ReturnType]:
    """
    Fix function to be used in the safe_call decorator for synchronous functions.

    This function is called when an exception occurs in the decorated function.
    It returns a FixFuncResult object with the error data.

    Returns:
        FixFuncResult: The result of the fix function.
    """
    source = inspect.getsource(func)
    filepath = inspect.getfile(func)

    if hasattr(func, "autofix") and func.autofix:
        if not (hasattr(func, "fix_agent") and hasattr(func.fix_agent, "run")):
            vc.fail(
                f"Error detected in function {func.__name__!r} but you have to wrap function with @agent.safe or @agent.safe_plain decorator to use autofix feature."
            )
            return error_data
        elif not hasattr(func.fix_agent, "run") or not func.fix_agent:
            vc.fail(
                f"Error detected in function {func.__name__!r} but you have to call set_fix_agent with your fix agent instance to use autofix feature."
            )
            return error_data

        vc.info(f"Autofixing error in function {func.__name__!r}...")
        vc.fail(f"Error detected in function [bold yellow]`{func.__name__!r}`[/]")

        user_prompt = generate_fix_message(
            source=source,
            filepath=filepath,
            error_data=error_data,
        )

        fix_result = func.fix_agent.run_sync(
            user_prompt=user_prompt,
            output_type=FixFuncResult
            | StructuredDict(FixFuncResult.model_json_schema())
            | str,
        )

        fix_time = datetime.now()

        if isinstance(fix_result.output, dict):
            result = fix_result.output
        elif hasattr(fix_result.output, "model_dump"):
            result = fix_result.output.model_dump()
        else:
            result = fix_result.output

        fix_data = {
            "filepath": filepath,
            "source": source,
            "function": func.__name__,
            "result": result,
            "fixdate": {
                "iso": fix_time.isoformat(),
                "unix": int(fix_time.timestamp()),
            },
        }

        func.fix_agent.fixdb.insert(fix_data)

        vc.info("Fix process ended successfully!")

        if func.autofix_options.reload_function:
            module_path = os.path.abspath(inspect.getfile(func))
            content = Path(module_path).read_text(encoding="utf-8")
            if not main_pattern.search(content):
                raise MainBlockNotFound(
                    f"Main block (`if __name__ == '__main__':`) not found in the file {module_path!r}. "
                    "When using reload_function=True, you must place function calls inside this main block. "
                    "Please ensure the file includes a proper main guard to avoid runtime issues."
                )

            module_name = os.path.splitext(os.path.basename(module_path))[0]
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.import_module(spec.name)

            updated_func = getattr(module, func.__name__, None)
            if updated_func is None:
                vc.fail(
                    f"Function {func.__name__!r} not found in module {module_name!r}."
                )
                return error_data
            vc.log(f"Function {func.__name__!r} reloaded successfully!")
            result = updated_func(*args, **kwargs)
            return result
    return error_data


def is_factory(func: Callable[[], ReturnType]) -> bool:
    """
    Check if the function is a factory function.

    A predicate function whether it has no positional arguments or all its parameters have default values.
    """
    if not callable(func):
        return False
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if param.default is inspect.Parameter.empty:
            return False
    return True


def dep_name(dep: Callable[..., ReturnType]) -> str:
    """
    Get the name of the dependency function.

    Args:
        dep (Callable[..., ReturnType]): The dependency function.

    Returns:
        str: The name of the dependency function.
    """
    name = getattr(dep, "__name__", dep.__class__.__name__)
    if not name.startswith("get_"):
        return name
    else:
        return name[4:]


def has_deps_param(fn: Callable[..., object], deps_type: type) -> bool:
    """
    Check if the function has a 'deps' parameter of a specific type.
    """
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)

    for name, _ in sig.parameters.items():
        if name == "deps":
            param_type = hints.get(name, None)
            if not param_type:
                raise InvalidDependencyParam(
                    f"Function {fn.__name__!r} must have a 'deps' parameter annotated with {deps_type.__name__}."
                )
            origin = get_base_type(fn, name)
            if origin is not deps_type and origin.__base__ is not deps_type:
                raise InvalidDependencyParam(
                    f"Function {fn.__name__!r} 'deps' parameter must be of type {deps_type.__name__}, "
                    f"but got {origin.__name__ if hasattr(origin, '__name__') else origin}."
                )
            return True
    return False


def has_context_param(fn: Callable[..., object]) -> bool:
    """
    Check if the function has a 'deps' parameter of a specific type.
    """

    head_param = next(iter(inspect.signature(fn).parameters), None)

    if head_param is None:
        raise InvalidContextParam(
            "Function must have at least one parameter and it must be annotated with RunContext."
        )

    head_param_type = get_type_hints(fn).get(head_param, None)
    if not head_param_type:
        raise InvalidContextParam(
            f"Function {fn.__name__!r} must have a context parameter as a first argument that is annotated with RunContext."
        )
    origin = get_base_type(fn, head_param)
    if origin is not RunContext:
        raise InvalidContextParam(
            f"Context parameter of function {fn.__name__!r} must be of type RunContext, "
            f"but got {origin.__name__ if hasattr(origin, '__name__') else origin}."
        )
    return True


def function_body_range(func: Callable[..., Any]) -> dict[str, int]:
    """
    Get the start and body line numbers of a function.

    Args:
        func: The function to analyze

    Returns:
        Object: Reach by attributes, start_line and actual_body_line.
    """
    source_lines, start_line = inspect.getsourcelines(func)

    body_index = next(
        (i + 1 for i, line in enumerate(source_lines) if '"""' in line and i > 2), 1
    )

    actual_body_line = start_line + body_index

    return Object(
        {
            "source": source_lines,
            "start_line": start_line,
            "actual_body_line": actual_body_line,
        }
    )


def extract_function_body(func: Callable[..., Any]) -> str:
    """
    Extract the body of a given function.

    Args:
        func (Callable[..., Any]): The function to extract the body from.

    Returns:
        str: The body of the function as a string.
    """
    body_info = function_body_range(func)
    source_lines = body_info.source
    start_line = body_info.start_line
    body_start_line = body_info.actual_body_line

    header_length = body_start_line - start_line

    return "".join(source_lines[header_length:])


def handle_deps(deps: Deps):
    """
    Handle dependencies for the agent.

    Args:
        deps (Deps): The dependencies to handle.

    Returns:
        Deps: The processed dependencies.
    """
    _output_deps = Deps()
    for k, v in deps.items():
        if callable(v):
            _output_deps[k] = safe_run(v)
    return _output_deps


def process_deps(args: tuple, func: Callable[..., ReturnType]) -> tuple[RunContext]:
    """
    Process dependencies for the function.
    Args:
        args (tuple): The arguments passed to the function.
        func (Callable[..., ReturnType]): The function to process dependencies for.
    Returns:
        tuple: The processed arguments with dependencies.
    """
    if is_context_tool(func) and getattr(func, "deps", None):
        ctx = args[0] if args else None
        tooldeps = Deps()
        if ctx := args[0] if args else None:
            ctx.deps = Deps({"main": ctx.deps}) if ctx.deps else Deps()
            tooldeps = handle_deps(func.deps)
            ctx.deps.update(tooldeps)
            ctx.deps.update({type(v): v for _, v in tooldeps.items()})
    return args
