"""
Sandbox client for executing code in a secure environment.
"""

import inspect
import json
import os
from pathlib import Path

import dotenv
from e2b_code_interpreter import Sandbox

dotenv.load_dotenv()

_request_timeout = int(os.environ.get("REQUEST_TIMEOUT", 0))


def load_sandbox_config():
    """
    Load sandbox configuration from JSON file.
    """
    config_path = Path("./.e2b/sandbox_config.json")

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        default_config = {
            k: v.default if v.default is not inspect.Parameter.empty else None
            for k, v in inspect.signature(Sandbox).parameters.items()
        }
        default_config["api_key"] = os.environ.get("E2B_API_KEY", "")
        config_path.write_text(json.dumps({"config": default_config}, indent=4))
        print(f"Created default sandbox config at {config_path}")
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8")).get("config", {})
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load sandbox config: {e}")
        return {}


try:
    sandbox = Sandbox(**load_sandbox_config())
except:
    sandbox = None
