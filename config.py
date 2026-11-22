"""Settings for server mode, read from environment variables (or .env).

`flask run` loads .env automatically because python-dotenv is installed.
There is deliberately no default SECRET_KEY: a known key would let anyone
forge the signed session cookie, so the app refuses to start without one.
"""
import os

PLACEHOLDER_KEY = "change-me"  # the value in .env.example
# A short or guessable key lets anyone forge session cookies (SEC-06).
# secrets.token_hex(32), as .env.example suggests, gives 64 characters.
MIN_KEY_LENGTH = 32


class ConfigError(RuntimeError):
    """Server mode is not configured safely."""


def load_config():
    key = os.environ.get("SECRET_KEY", "")
    if key == PLACEHOLDER_KEY or len(key) < MIN_KEY_LENGTH:
        raise ConfigError(f"Set SECRET_KEY in .env to a random value of at least {MIN_KEY_LENGTH}"
                          " characters (see .env.example) before starting the server.")
    return {"SECRET_KEY": key}
