from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from autocoin.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode and foreign keys for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    from autocoin.models import (  # noqa: F401 - registers models
        alias_rule,
        classification_rule,
        import_batch,
        transaction,
        user,
        user_preference,
    )
    Base.metadata.create_all(bind=engine)
    _ensure_lightweight_migrations()


def _ensure_lightweight_migrations():
    inspector = inspect(engine)
    if "transactions" not in inspector.get_table_names():
        return
    tx_columns = {col["name"] for col in inspector.get_columns("transactions")}
    with engine.begin() as conn:
        if "product_alias" not in tx_columns:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN product_alias VARCHAR(128)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_product_alias ON transactions (product_alias)"))
        if "finishrefundcheck" not in tx_columns:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN finishrefundcheck INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_finishrefundcheck ON transactions (finishrefundcheck)"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
