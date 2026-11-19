import os

# Games are kept in memory during tests; this is read when app.py is imported.
os.environ["DATA_DIR"] = ""
os.environ["NEW_GAMES_PER_HOUR"] = "0"  # tests make plenty of games; the limit has its own tests
