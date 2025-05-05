import os
import sys

# Add src directory to PYTHONPATH for imports
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
import tempfile

# Use a fresh SQLite database file for each test session to avoid test pollution
fd, db_path = tempfile.mkstemp(prefix="nagatha_test_", suffix=".db")
os.close(fd)
os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"