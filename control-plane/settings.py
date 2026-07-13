"""
settings.py -- centralized, env-driven configuration.

One place for the knobs an operator tunes at deploy time. Everything reads from
the environment with sensible defaults, so nothing needs code changes to run in
a different environment.
"""

import os


class Settings:
    app_name = "AEGIS Control Plane"
    version = "0.4.0"

    # MFA/OAuth session lifetime
    session_ttl_seconds = int(os.environ.get("AEGIS_SESSION_TTL", "3600"))

    # logging
    log_level = os.environ.get("AEGIS_LOG_LEVEL", "INFO").upper()

    # CORS: origins allowed to call the API directly (the dashboard dev server).
    # Comma-separated; the Vite proxy path works without this, but a deployed
    # dashboard on a different origin needs it.
    cors_origins = [o for o in
                    os.environ.get("AEGIS_CORS_ORIGINS",
                                   "http://localhost:5174,http://127.0.0.1:5174").split(",")
                    if o]


settings = Settings()
