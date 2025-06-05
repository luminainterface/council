"""
Redis RDB to SQLite converter for traffic snapshot pipeline.
Parses Redis backup files and extracts prompt/response queues into SQLite database.
"""

import sys, json, sqlite3, hashlib
from rdbtools import RdbParser, MemoryCallback

PROMPT_KEY = "prompt_queue"
RESP_KEY   = "response_queue"     # if you push paired responses

class _Callback(MemoryCallback):
    def __init__(self):
        super().__init__()
        self.prompts, self.responses = [], []

    def list(self, key, length, items):
        if key == PROMPT_KEY:
            self.prompts = items
        elif key == RESP_KEY:
            self.responses = items

def sha1(t): return hashlib.sha1(t.encode()).hexdigest()

def main(rdb_path, sqlite_path):
    cb = _Callback()
    RdbParser(cb).parse(open(rdb_path, 'rb'))
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS prompts (
        id TEXT PRIMARY KEY,
        text TEXT, cluster_id TEXT
    );
    CREATE TABLE IF NOT EXISTS responses (
        id TEXT PRIMARY KEY,
        text TEXT
    );
    """)
    for i,p in enumerate(cb.prompts):
        cid = None  # will be filled by join query later
        pid = sha1(p + str(i))
        cur.execute("INSERT OR IGNORE INTO prompts VALUES (?,?,?)", (pid,p,cid))
    for i,r in enumerate(cb.responses):
        rid = sha1(r + str(i))
        cur.execute("INSERT OR IGNORE INTO responses VALUES (?,?)", (rid,r))
    conn.commit(); conn.close()

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2]) 