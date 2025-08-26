"""
Constants and schemes for the Venus application.
"""

serve_command = "uvicorn {module}:{app}.api --host {host} --port {port} --reload"

server_config = {
    "host": {"dev": "127.0.0.1", "prod": "0.0.0.0"},
    "port": {"dev": 1283, "prod": 80},
}

color_map = {
    "INFO": "green",
    "WARN": "yellow",
    "FAIL": "red",
}
