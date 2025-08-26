from datetime import datetime
from typing import Literal

from rich.console import Console

from .constants import color_map


class BaseConsole(Console):
    """
    Base console class that extends the Rich Console.
    This can be used to add custom logging or output formatting.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fmt = "[bold green]{loglevel}[/]:     {message}"

    def logger(
        self,
        loglevel: Literal["INFO", "WARN"] = "INFO",
        *,
        message: str | None = None,
        color: str = "green",
        bold: bool = True,
    ) -> None:
        """
        Log a message with the specified log level, color, and bold formatting.
        """
        if not message:
            return self.print()
        if bold:
            message = f"[bold {color}]{message}[/]"
        else:
            message = f"[{color}]{message}[/]"
        loglevel = f"[{color_map.get(loglevel, 'green')}]{loglevel}"
        return self.print(self.fmt.format(loglevel=loglevel, message=message))

    def info(
        self,
        message: str | None = None,
        color: str = "green",
        bold: bool = True,
    ):
        """
        Log an info message.
        """
        return self.logger("INFO", message=message, color=color, bold=bold)

    def warn(
        self, message: str | None = None, color: str = "yellow", bold: bool = True
    ):
        """
        Log a warning message.
        """
        return self.logger("WARN", message=message, color=color, bold=bold)

    def fail(self, message: str | None = None, color: str = "red", bold: bool = True):
        """
        Placeholder for a method to fail the console.
        This can be overridden in subclasses if needed.
        """
        return self.logger("FAIL", message=message, color=color, bold=bold)


class VenusConsole(BaseConsole):
    """
    Custom console for Venus that extends the Rich Console.
    This can be used to add custom logging or output formatting.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.venus_fmt = "[green]{time}[/] {message}"

    def log(
        self,
        message: str,
        bold: bool = False,
        color: str = "green",
        level_color: str = "green",
    ):
        """
        Log a message with the current time.
        """
        if bold:
            message = f"[bold {color}]{message}[/]"
        else:
            message = f"[{color}]{message}[/]"
        fmt = (
            self.venus_fmt
            if level_color == "green"
            else self.venus_fmt.replace("[green]{time}", "[%s]{time}" % level_color)
        )
        self.print(
            fmt.format(
                time=datetime.now().strftime("%H:%M:%S.%f")[:-3], message=message
            )
        )
