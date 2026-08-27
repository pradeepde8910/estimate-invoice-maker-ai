import os

# No hardcoded fallback — v1/config.py already refuses to start without a
# real JWT_SECRET; mirroring that here (rather than a default like
# "supersecretkey") means this module can never become the weak link if it's
# ever imported/used before v1.config, in a script, or in a test that
# doesn't go through the main app's startup path.
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set. Generate one (e.g. `python -c \"import secrets; "
        "print(secrets.token_urlsafe(48))\"`) and set it in your .env file - "
        "the app refuses to start with no signing secret rather than fall "
        "back to a value that used to be hardcoded in source."
    )

# Mirrors v1/config.py's ADMIN_USERNAME/QA_TEST_USERNAME (same env vars) so
# app/api/dependencies.py can resolve the QA X-API-Key identity without
# depending on v1's module being importable as bare `config`.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
QA_TEST_USERNAME = os.environ.get("QA_TEST_USERNAME", ADMIN_USERNAME)
