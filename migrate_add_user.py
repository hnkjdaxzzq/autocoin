"""
Migration: Add user_id columns to transactions and import_batches.
Creates a default user and assigns all existing data to them.
Run once: uv run python migrate_add_user.py
"""
import sqlite3
from pathlib import Path

import bcrypt

DB_PATH = Path(__file__).parent / "autocoin.db"


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def migrate():
    if not DB_PATH.exists():
        print("Database not found. No migration needed (tables will be created on first run).")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # 1. Create users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(128) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Create default user
    default_hash = _hash_password("changeme123")
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
        ("admin", default_hash),
    )
    default_user_id = cur.execute(
        "SELECT id FROM users WHERE username = 'admin'"
    ).fetchone()[0]

    # 3. Add user_id column to transactions (with default)
    try:
        cur.execute(
            "ALTER TABLE transactions ADD COLUMN user_id INTEGER DEFAULT ?",
            (default_user_id,),
        )
    except sqlite3.OperationalError:
        pass  # column already exists

    # 4. Set user_id on all existing rows
    cur.execute(
        "UPDATE transactions SET user_id = ? WHERE user_id IS NULL",
        (default_user_id,),
    )

    # 5. Add user_id column to import_batches
    try:
        cur.execute(
            "ALTER TABLE import_batches ADD COLUMN user_id INTEGER DEFAULT ?",
            (default_user_id,),
        )
    except sqlite3.OperationalError:
        pass

    cur.execute(
        "UPDATE import_batches SET user_id = ? WHERE user_id IS NULL",
        (default_user_id,),
    )

    # 6. Recreate unique constraint as (user_id, source, source_order_id)
    cur.execute("DROP INDEX IF EXISTS uq_source_order")
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_source_order
        ON transactions (user_id, source, source_order_id)
    """)

    # 7. Create indexes on user_id
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_transactions_user_id ON transactions (user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_import_batches_user_id ON import_batches (user_id)"
    )

    conn.commit()
    conn.close()

    print(f"Migration complete. Default user 'admin' (id={default_user_id}) created.")
    print("All existing data assigned to default user.")
    print("IMPORTANT: Change the default password (changeme123) after first login!")


if __name__ == "__main__":
    migrate()
