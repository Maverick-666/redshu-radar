import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path, migration_path: Path | None = None) -> None:
        self.path = path
        migration_root = Path(__file__).resolve().parents[3] / "migrations"
        self._uses_default_migrations = migration_path is None
        self.migration_path = migration_path or migration_root / "001_initial.sql"
        self.taxonomy_migration_path = migration_root / "002_taxonomy.sql"

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            if not self._uses_default_migrations:
                connection.executescript(
                    self.migration_path.read_text(encoding="utf-8")
                )
                return
            migration_sql = "\n".join(
                (
                    "BEGIN IMMEDIATE;",
                    self.migration_path.read_text(encoding="utf-8"),
                    self.taxonomy_migration_path.read_text(encoding="utf-8"),
                )
            )
            connection.executescript(migration_sql)
            product_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(products)")
            }
            if "category_id" not in product_columns:
                connection.execute(
                    """
                    ALTER TABLE products
                    ADD COLUMN category_id INTEGER
                        REFERENCES categories(id) ON DELETE RESTRICT
                    """
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_products_category "
                "ON products(category_id)"
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
