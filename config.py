"""Settings for server mode, read from environment variables (or .env).

`flask run` loads .env automatically because python-dotenv is installed.
There is deliberately no default SECRET_KEY: a known key would let anyone
forge the signed session cookie, so the app refuses to start without one.
"""
import os

PLACEHOLDER_KEY = "change-me"  # the value in .env.example


class ConfigError(RuntimeError):
    """Server mode is not configured safely."""


def load_config():
    key = os.environ.get("SECRET_KEY", "")
    if not key or key == PLACEHOLDER_KEY:
        raise ConfigError("Set SECRET_KEY in .env (see .env.example) before starting the server.")
    return {"SECRET_KEY": key}
