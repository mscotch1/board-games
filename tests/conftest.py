import os

# Games are kept in memory during tests; this is read when app.py is imported.
os.environ["DATA_DIR"] = ""
