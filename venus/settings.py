import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from .prompts import CODING_PROMPT, CUSTOM_FIX_PROMPT, FIX_PROMPT

# Determine the default path for Claude configuration based on the operating system
if os.name == "nt":
    default_claude_path = "$env:AppData/Roaming/Claude/claude_desktop_config.json"
else:
    home_dir = Path.home()
    default_claude_path = str(
        home_dir / "Library/Application Support/Claude/claude_desktop_config.json"
    )
    del home_dir


class Settings(BaseSettings):
    """
    Settings for the Venus application.

    This class retrieves configuration settings from environment variables or a .env file.
    """

    # API keys for LLM providers
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    groq_api_key: str = Field(default="", description="Groq API key")
    xai_api_key: str = Field(default="", description="xAI API key")
    grok_api_key: str = Field(default="", description="Grok API key")
    openai_api_key: str = Field(default="", description="OpenAI API key")
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    google_api_key: str = Field(default="", description="Google API key")

    # Utility API Keys

    e2b_api_key: str = Field(default="", description="E2B API key for code execution")

    # Path to the Claude configuration file
    claude_config_path: str = Field(
        default=default_claude_path, description="Path to the Claude configuration file"
    )

    # Prompts for the agent
    system_prompt: str = Field(
        default="Your name is Venus, an AI Agent. You are a helpful assistant.",
        description="System prompt for the agent",
    )

    coding_prompt: str = Field(
        default=CODING_PROMPT, description="Coding prompt for the agent"
    )

    custom_fix_prompt: str = Field(
        default=CUSTOM_FIX_PROMPT, description="Custom prompt for fixing errors, if any"
    )

    default_fix_prompt: str = Field(
        default=FIX_PROMPT, description="Default prompt for fixing errors"
    )

    # Server settings
    server_host: str = Field(default="127.0.0.1", description="Host for the server")
    server_port: int = Field(default=1283, description="Port for the server")

    # Model settings
    fix_model: str = Field(default="", description="Default model for fixing code")

    model_name: str = Field(
        default="grok-3-mini", description="Default model name for the agent"
    )

    agent_name: str = Field(default="venus", description="Name of the AI Agent")

    # Provider settings
    grok_base_url: str = Field(
        default="https://api.x.ai/v1", description="Base URL for the Grok API"
    )

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434/v1", description="Base URL for the Ollama API"
    )

    lmstudio_base_url: str = Field(
        default="http://127.0.0.1:1234/v1", description="Base URL for the LMStudio API"
    )

    model_config = {"extra": "ignore", "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
