import os

# the automatic sync must not start while tests run
os.environ.setdefault("SYNC_INTERVAL_HOURS", "0")
