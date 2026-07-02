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
        stock_api_cache,
        stock_data,
        stock_query_cache,
        transaction,
        user,
        user_preference,
    )
    Base.metadata.create_all(bind=engine)
    _ensure_lightweight_migrations()


def _ensure_lightweight_migrations():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    with engine.begin() as conn:
        if "transactions" in table_names:
            tx_columns = {col["name"] for col in inspector.get_columns("transactions")}
            if "product_alias" not in tx_columns:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN product_alias VARCHAR(128)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_product_alias ON transactions (product_alias)"))
            if "finishrefundcheck" not in tx_columns:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN finishrefundcheck INTEGER NOT NULL DEFAULT 0"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_finishrefundcheck ON transactions (finishrefundcheck)"))
            if "is_ai_classified" not in tx_columns:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN is_ai_classified INTEGER NOT NULL DEFAULT 0"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_is_ai_classified ON transactions (is_ai_classified)"))
        if "stockdata" in table_names:
            stock_columns = {col["name"] for col in inspector.get_columns("stockdata")}
            if "stock_transaction_date" not in stock_columns:
                conn.execute(text("ALTER TABLE stockdata ADD COLUMN stock_transaction_date DATETIME"))
            if "stock_entry_time" not in stock_columns:
                conn.execute(text("ALTER TABLE stockdata ADD COLUMN stock_entry_time DATETIME"))
                conn.execute(text("UPDATE stockdata SET stock_entry_time = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE stock_entry_time IS NULL"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_stockdata_stock_transaction_date ON stockdata (stock_transaction_date)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_stockdata_stock_entry_time ON stockdata (stock_entry_time)"))
        if "stock_api_cache" in table_names:
            cache_columns = {col["name"] for col in inspector.get_columns("stock_api_cache")}
            if "raw_api_source" not in cache_columns:
                conn.execute(text("ALTER TABLE stock_api_cache ADD COLUMN raw_api_source VARCHAR(32)"))
            if "raw_api_data" not in cache_columns:
                conn.execute(text("ALTER TABLE stock_api_cache ADD COLUMN raw_api_data TEXT"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
