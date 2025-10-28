import sys, os
# Ensure project root is in sys.path for module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from jewel.config import settings
from jewel.memory.sqlite_store import SqliteStore

# Initialize the SQLite store
store = SqliteStore(settings.db_path)

# Retrieve and print the last recorded OpenAI and video errors
print("last_openai_error:", store.get("last_openai_error"))
print("last_video_error:", store.get("last_video_error"))