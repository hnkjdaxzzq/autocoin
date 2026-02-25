"""Shared test configuration. Must set env vars BEFORE any autocoin imports."""
import os
import shutil
import tempfile

# Create a unique temporary directory for the test database.
# This MUST happen before any autocoin modules are imported,
# because autocoin.config.Settings() and autocoin.database.engine
# are created at module-level import time.
_test_db_dir = tempfile.mkdtemp(prefix="autocoin_test_")
_test_db_path = os.path.join(_test_db_dir, "test.db")

os.environ["AUTOCOIN_DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["AUTOCOIN_JWT_SECRET"] = "test-secret-key-for-testing"


def pytest_sessionfinish(session, exitstatus):
    """Clean up the temporary test database directory after all tests."""
    if os.path.exists(_test_db_dir):
        shutil.rmtree(_test_db_dir, ignore_errors=True)
