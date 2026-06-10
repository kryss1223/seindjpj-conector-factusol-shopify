import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings


class IdempotencyService:
    """
    Guarda el estado de pedidos Shopify procesados para evitar duplicados.

    En produccion se recomienda DATABASE_URL con PostgreSQL. El fallback SQLite
    permite probar el flujo en local sin meter mas piezas.
    """

    def __init__(self) -> None:
        self.database_url = settings.database_url
        self.sqlite_path = Path(settings.sqlite_idempotency_path)

    def start_processing(
        self,
        shopify_order_id: str,
        shopify_order_name: str | None,
    ) -> dict[str, Any]:
        if self.database_url:
            return self._postgres_start_processing(shopify_order_id, shopify_order_name)

        return self._sqlite_start_processing(shopify_order_id, shopify_order_name)

    def _sqlite_start_processing(
        self,
        shopify_order_id: str,
        shopify_order_name: str | None,
    ) -> dict[str, Any]:
        self._ensure_sqlite_schema()

        try:
            self._insert_order(
                shopify_order_id=shopify_order_id,
                shopify_order_name=shopify_order_name,
                status="processing",
            )
            return {"status": "processing"}
        except sqlite3.IntegrityError:
            pass

        existing = self.get_order(shopify_order_id)

        if existing:
            if existing["status"] == "processed":
                return {
                    "status": "already_processed",
                    "factusol_order_code": existing.get("factusol_order_code"),
                }

            if existing["status"] == "processing":
                return {"status": "already_processing"}

            self._update_order(
                shopify_order_id=shopify_order_id,
                status="processing",
                error_message=None,
            )
            return {"status": "processing"}

        return {"status": "processing"}

    def _postgres_start_processing(
        self,
        shopify_order_id: str,
        shopify_order_name: str | None,
    ) -> dict[str, Any]:
        import psycopg
        from psycopg.rows import dict_row

        self._ensure_postgres_schema()

        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO processed_shopify_orders (
                        shopify_order_id, shopify_order_name, status, created_at, updated_at
                    )
                    VALUES (%s, %s, 'processing', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (shopify_order_id) DO NOTHING
                    RETURNING shopify_order_id
                    """,
                    (shopify_order_id, shopify_order_name),
                )

                if cursor.fetchone():
                    return {"status": "processing"}

                cursor.execute(
                    """
                    SELECT shopify_order_id, shopify_order_name, status,
                           factusol_order_code, error_message
                    FROM processed_shopify_orders
                    WHERE shopify_order_id = %s
                    FOR UPDATE
                    """,
                    (shopify_order_id,),
                )
                existing = cursor.fetchone()

                if existing["status"] == "processed":
                    return {
                        "status": "already_processed",
                        "factusol_order_code": existing.get("factusol_order_code"),
                    }

                if existing["status"] == "processing":
                    return {"status": "already_processing"}

                cursor.execute(
                    """
                    UPDATE processed_shopify_orders
                    SET status = 'processing',
                        error_message = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE shopify_order_id = %s
                    """,
                    (shopify_order_id,),
                )

                return {"status": "processing"}

    def mark_processed(
        self,
        shopify_order_id: str,
        factusol_order_code: int | None,
    ) -> None:
        self._update_order(
            shopify_order_id=shopify_order_id,
            status="processed",
            factusol_order_code=factusol_order_code,
            error_message=None,
        )

    def mark_manual_review(
        self,
        shopify_order_id: str,
        error_message: str | None,
    ) -> None:
        self._update_order(
            shopify_order_id=shopify_order_id,
            status="manual_review_required",
            error_message=error_message,
        )

    def mark_failed(
        self,
        shopify_order_id: str,
        error_message: str | None,
    ) -> None:
        self._update_order(
            shopify_order_id=shopify_order_id,
            status="failed",
            error_message=error_message,
        )

    def get_order(self, shopify_order_id: str) -> dict[str, Any] | None:
        if self.database_url:
            return self._postgres_get_order(shopify_order_id)

        self._ensure_sqlite_schema()
        with closing(sqlite3.connect(self.sqlite_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT shopify_order_id, shopify_order_name, status,
                       factusol_order_code, error_message
                FROM processed_shopify_orders
                WHERE shopify_order_id = ?
                """,
                (shopify_order_id,),
            ).fetchone()

        return dict(row) if row else None

    def _insert_order(
        self,
        shopify_order_id: str,
        shopify_order_name: str | None,
        status: str,
    ) -> None:
        if self.database_url:
            self._postgres_insert_order(shopify_order_id, shopify_order_name, status)
            return

        self._ensure_sqlite_schema()
        now = self._now()
        with closing(sqlite3.connect(self.sqlite_path)) as connection:
            connection.execute(
                """
                INSERT INTO processed_shopify_orders (
                    shopify_order_id, shopify_order_name, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (shopify_order_id, shopify_order_name, status, now, now),
            )
            connection.commit()

    def _update_order(
        self,
        shopify_order_id: str,
        status: str,
        factusol_order_code: int | None = None,
        error_message: str | None = None,
    ) -> None:
        if self.database_url:
            self._postgres_update_order(
                shopify_order_id=shopify_order_id,
                status=status,
                factusol_order_code=factusol_order_code,
                error_message=error_message,
            )
            return

        self._ensure_sqlite_schema()
        with closing(sqlite3.connect(self.sqlite_path)) as connection:
            connection.execute(
                """
                UPDATE processed_shopify_orders
                SET status = ?,
                    factusol_order_code = COALESCE(?, factusol_order_code),
                    error_message = ?,
                    updated_at = ?
                WHERE shopify_order_id = ?
                """,
                (status, factusol_order_code, error_message, self._now(), shopify_order_id),
            )
            connection.commit()

    def _ensure_sqlite_schema(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.sqlite_path)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_shopify_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shopify_order_id TEXT NOT NULL UNIQUE,
                    shopify_order_name TEXT,
                    status TEXT NOT NULL,
                    factusol_order_code INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def _postgres_get_order(self, shopify_order_id: str) -> dict[str, Any] | None:
        import psycopg
        from psycopg.rows import dict_row

        self._ensure_postgres_schema()
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT shopify_order_id, shopify_order_name, status,
                           factusol_order_code, error_message
                    FROM processed_shopify_orders
                    WHERE shopify_order_id = %s
                    """,
                    (shopify_order_id,),
                )
                return cursor.fetchone()

    def _postgres_insert_order(
        self,
        shopify_order_id: str,
        shopify_order_name: str | None,
        status: str,
    ) -> None:
        import psycopg

        self._ensure_postgres_schema()
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO processed_shopify_orders (
                        shopify_order_id, shopify_order_name, status, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (shopify_order_id) DO NOTHING
                    """,
                    (shopify_order_id, shopify_order_name, status),
                )

    def _postgres_update_order(
        self,
        shopify_order_id: str,
        status: str,
        factusol_order_code: int | None,
        error_message: str | None,
    ) -> None:
        import psycopg

        self._ensure_postgres_schema()
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE processed_shopify_orders
                    SET status = %s,
                        factusol_order_code = COALESCE(%s, factusol_order_code),
                        error_message = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE shopify_order_id = %s
                    """,
                    (status, factusol_order_code, error_message, shopify_order_id),
                )

    def _ensure_postgres_schema(self) -> None:
        import psycopg

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS processed_shopify_orders (
                        id SERIAL PRIMARY KEY,
                        shopify_order_id TEXT NOT NULL UNIQUE,
                        shopify_order_name TEXT,
                        status TEXT NOT NULL,
                        factusol_order_code INTEGER,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()
