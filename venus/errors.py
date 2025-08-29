from typing import Any, Optional, TypeVar, Union

from pydantic import BaseModel
from typing_extensions import TypedDict

"""
Error types for the Agent.
"""


class FrameInfo(TypedDict):
    """
    Represents the frame information where an error occurred.

    Attributes:
        lineno (int): Line number of the error.
        filename (str): File name where the error occurred.
        caller (str): Function that called the current function.
        context (Optional[Union[str, list[str]]]): Context of the error, can be a string or a list of strings.
    """

    lineno: int
    filename: str
    caller: str
    context: Optional[Union[str, list[str]]]


class ErrorDict(BaseModel):
    """
    Represents an error dictionary containing details about the error.

    Attributes:
        status    (str): Status of the error.
        function  (str): Name of the function where the error occurred.
        exception (str): The error that occurred.
        frame_info (Optional[FrameInfo]): Frame information where the error occurred.
    """

    status: Optional[str] = "error"
    function: Optional[str] = None
    exception: Optional[str] = "An error occurred"
    frame_info: Optional[FrameInfo] = None

    model_config = {"arbitrary_types_allowed": True}

    def __repr__(self):
        return (
            f"ErrorDict(function={self.function!r}, status={self.status!r}, "
            f"exception={self.exception!r}, frame_info={self.frame_info!r})"
        )

    def __str__(self):
        caller = self.caller if self.caller != self.function else "self"
        return (
            f"The `{self.function}` function called by `{caller}` and raised "
            f"{self.exception} at {self.location}"
        )

    @property
    def location(self) -> Optional[str]:
        """Get the location of the error."""
        if self.frame_info:
            return f"{self.frame_info['filename']}:{self.frame_info['lineno']}"
        return None

    @property
    def filename(self) -> Optional[str]:
        """Get the filename of the error."""
        if self.frame_info:
            return self.frame_info["filename"]
        return None

    @property
    def lineno(self) -> Optional[int]:
        """Get the line number of the error."""
        if self.frame_info:
            return self.frame_info["lineno"]
        return None

    @property
    def caller(self) -> Optional[str]:
        """Get the caller of the error."""
        if self.frame_info:
            return self.frame_info["caller"]
        return None

    @property
    def context(self) -> Optional[Union[str, list[str]]]:
        """Get the context of the error."""
        if self.frame_info:
            return self.frame_info["context"]
        return None

    @property
    def message(self) -> str:
        """Get a serialized error message."""
        return (
            f"Error occured in `{self.function}`: {self.exception} at {self.location}.\n"
            f"Code context: {self.context}"
        )


T = TypeVar("T", bound=BaseModel | Any)

SafeResult = Union[T, ErrorDict]


class ProviderConflict(ValueError):
    """
    Raised when both `provider_options` and `custom_provider` are set simultaneously.
    """

    pass


class InvalidProvider(TypeError):
    """
    Raised when the passed provider is not valid.
    """

    pass


class InvalidTool(ValueError):
    """
    Raised when the tool does not meet the required criteria.
    """

    pass


class InvalidModuleName(ValueError):
    """
    Raised when the module name does not conform to expected standards.
    """

    pass


class ModuleImportError(ImportError):
    """
    Raised when there is an error importing a module.
    """

    pass


class InvalidTools(TypeError):
    """
    Raised when the toolset is not iterable.
    """

    pass


class InvalidFilePath(FileNotFoundError):
    """
    Raised when the specified file path does not exist or is not accessible.
    """

    pass


class InvalidContextParam(ValueError):
    """
    Raised when the context parameter is not the first parameter or is not annotated with `RunContext[...]`.
    """

    pass


class InvalidDependencyParam(ValueError):
    """
    Raised when a dependency parameter is not properly annotated with `Deps[...]` or cannot be resolved as a dependency.
    """

    pass


class InvalidFunction(ValueError):
    """
    Raised when the function does not meet the required criteria.
    This can include issues like missing parameters, incorrect annotations, etc.
    """

    pass


class ContextParamDuplicated(InvalidContextParam):
    """
    Raised when the function has more than one context parameter but expects `RunContext` as the first parameter.
    """

    pass


class ModuleNotImported(ModuleImportError):
    """
    Raised when the module is not imported.
    """

    pass


class ModuleRaisedException(ModuleImportError):
    """
    Raised when the module raises an exception during import.
    """

    pass


class MainBlockNotFound(ModuleImportError):
    """
    Raised when the main block is not found in the file.

    This is particularly relevant when using `reload_function=True` in decorators,
    as it requires the function calls to be within an `if __name__ == "__main__:` block.
    """

    pass


class ExecutionNotAllowed(ValueError):
    """
    Raised when code execution is not allowed.

    This is used to prevent code execution in environments where it is not permitted.
    """

    pass


class InvalidParameter(ValueError):
    """
    Raised when a parameter does not meet the required criteria.

    This can include issues like missing annotations, incorrect types, etc.
    """

    pass
