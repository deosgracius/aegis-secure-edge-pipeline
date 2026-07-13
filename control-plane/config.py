"""
config.py -- runtime configuration (Google OAuth credentials).

Reads from the environment first; falls back to the project-root .env.txt during
local dev. Secrets are NEVER hardcoded here or committed — this only reads them.
"""

import os

_ENV_CACHE = None


def _load_env_file():
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE
    _ENV_CACHE = {}
    # project root is two levels up from control-plane/ (SummerProject/.env.txt)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", ".env.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _ENV_CACHE[k.strip()] = v.strip().strip('"').strip("'")
    return _ENV_CACHE


def get(key, default=""):
    """Env var wins; then .env.txt; then default."""
    if os.environ.get(key):
        return os.environ[key]
    return _load_env_file().get(key, default)


def google_oauth():
    return {
        "client_id": get("GOOGLE_CLIENT_ID"),
        "client_secret": get("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": get("GOOGLE_REDIRECT_URI",
                            "http://localhost:8000/auth/oauth/callback"),
    }


def oauth_configured():
    c = google_oauth()
    return bool(c["client_id"] and c["client_secret"])
