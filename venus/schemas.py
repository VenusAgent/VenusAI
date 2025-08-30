"""
Internal output schemas for the Agent.
"""

from typing import List, Optional, Union

from pydantic import BaseModel, Field

from .errors import ErrorDict


class CodeRunResult(BaseModel):
    """
    Represents the result of a code execution.

    Attributes:
        created_file_paths (Optional[List[str]]): List of file paths created during
            the execution, if any.
        project_build_command (Optional[Union[str, List[str]]]): Build and install commands
            as an ordered list of strings.
        project_start_command (Optional[Union[str, List[str]]]): Start command(s) for the project,
            if applicable.
        raw_output (Optional[str]): Raw output of the agent.
        errors (Optional[ErrorDict]): Error details if the tool raises an exception.
    """

    created_file_paths: Optional[List[str]] = Field(
        default=None, description="List of file paths during agent tool calls, if any."
    )
    project_build_command: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Build and install combined commands as ordered list of strings.",
    )
    project_start_command: Optional[Union[str, List[str]]] = Field(
        default=None, description="Start commands for the project, if applicable."
    )
    raw_output: Optional[str] = Field(
        default=None, description="Raw output of the agent."
    )
    errors: Optional[ErrorDict] = Field(
        default=None,
        description="If tool raises an exception, this will return an ErrorDict with the error details.",
    )


class FixFuncResult(BaseModel):
    """
    Represents the result of a function fix operation.

    Attributes:
        original_function_body (Optional[str]): The original function body before any modifications.
        fixed_function_body (Optional[str]): The function body after applying fixes.
        modified_lines (Optional[List[int]]): Line numbers that were modified during the fix process.
        errors_fixed (Optional[bool]): Indicates if the errors were successfully resolved.
        found_issues (List[str]): List of issues identified in the function.
    """

    original_function_body: Optional[str] = Field(
        ..., description="The original function body before any modifications."
    )
    fixed_function_body: Optional[str] = Field(
        ..., description="Final function body after modifications."
    )
    modified_lines: Optional[List[int]] = Field(
        default=None, description="Line numbers that were modified during the fix."
    )
    errors_fixed: Optional[bool] = Field(
        default=None, description="Indicates whether errors were successfully resolved."
    )
    found_issues: List[str] = Field(
        default_factory=list, description="A list of issues found in the function."
    )


class DoesNeedFix(BaseModel):
    """
    Represents whether a function needs fixing.

    Attributes:
        needs_fix (bool): Indicates if the function needs fixing.
        issues (List[str]): List of issues found in the function.
    """

    needs_fix: bool = Field(
        default=False, description="Indicates if the function needs fixing."
    )
    errors: List[str] = Field(
        default_factory=list, description="List of errors found in the function."
    )
