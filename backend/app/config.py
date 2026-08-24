import os

JWT_SECRET = os.environ.get("JWT_SECRET", "supersecretkey")

# Mirrors v1/config.py's ADMIN_USERNAME/QA_TEST_USERNAME (same env vars) so
# app/api/dependencies.py can resolve the QA X-API-Key identity without
# depending on v1's module being importable as bare `config`.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
QA_TEST_USERNAME = os.environ.get("QA_TEST_USERNAME", ADMIN_USERNAME)
