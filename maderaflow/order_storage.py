"""SQLite persistence for order-intake requests and notification state.

SQLite keeps the first milestone dependency-free and testable. A production
deployment must point ``ORDER_DATABASE_PATH`` at durable storage or replace
this repository with a managed database implementation.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

from maderaflow.models import OrderIntakeRequest


class SQLiteOrderRepository:
    """Create idempotent order requests with a daily country sequence."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_order_sequences (
                country_code TEXT NOT NULL,
                local_date TEXT NOT NULL,
                last_value INTEGER NOT NULL,
                PRIMARY KEY (country_code, local_date)
            );

            CREATE TABLE IF NOT EXISTS order_requests (
                request_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL UNIQUE,
                country_code TEXT NOT NULL,
                language_code TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                spanish_summary TEXT NOT NULL,
                escalation_json TEXT NOT NULL,
                whatsapp_message TEXT NOT NULL,
                whatsapp_delivery_status TEXT NOT NULL,
                alert_visible INTEGER NOT NULL DEFAULT 0
            );
            """
        )

    def create(
        self,
        request: OrderIntakeRequest,
        *,
        country_code: str,
        language_code: str,
        status: str,
        spanish_summary: str,
        escalation_reasons: list[str],
        whatsapp_message_factory: Callable[[str], str],
        whatsapp_delivery_status: str,
        alert_visible: bool,
        now_utc: datetime,
        local_date: str,
    ) -> dict[str, Any]:
        """Save one request and return an existing one on webhook retries."""
        with self._connect() as connection:
            self._initialize(connection)
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT request_id, status, whatsapp_delivery_status, alert_visible
                FROM order_requests
                WHERE conversation_id = ?
                """,
                (request.conversation_id,),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return {
                    "request_id": existing["request_id"],
                    "status": existing["status"],
                    "whatsapp_delivery_status": existing[
                        "whatsapp_delivery_status"
                    ],
                    "alert_visible": bool(existing["alert_visible"]),
                    "created": False,
                }

            sequence_row = connection.execute(
                """
                SELECT last_value
                FROM daily_order_sequences
                WHERE country_code = ? AND local_date = ?
                """,
                (country_code, local_date),
            ).fetchone()
            next_value = 1 if sequence_row is None else sequence_row["last_value"] + 1
            connection.execute(
                """
                INSERT INTO daily_order_sequences(country_code, local_date, last_value)
                VALUES (?, ?, ?)
                ON CONFLICT(country_code, local_date)
                DO UPDATE SET last_value = excluded.last_value
                """,
                (country_code, local_date, next_value),
            )
            request_id = (
                f"MLG-{country_code}-{local_date.replace('-', '')}-{next_value:04d}"
            )
            whatsapp_message = whatsapp_message_factory(request_id)
            connection.execute(
                """
                INSERT INTO order_requests(
                    request_id,
                    conversation_id,
                    country_code,
                    language_code,
                    status,
                    created_at_utc,
                    payload_json,
                    spanish_summary,
                    escalation_json,
                    whatsapp_message,
                    whatsapp_delivery_status,
                    alert_visible
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    request.conversation_id,
                    country_code,
                    language_code,
                    status,
                    now_utc.isoformat(),
                    json.dumps(request.model_dump(mode="json"), ensure_ascii=False),
                    spanish_summary,
                    json.dumps(escalation_reasons, ensure_ascii=False),
                    whatsapp_message,
                    whatsapp_delivery_status,
                    int(alert_visible),
                ),
            )
            connection.commit()
            return {
                "request_id": request_id,
                "status": status,
                "whatsapp_delivery_status": whatsapp_delivery_status,
                "alert_visible": alert_visible,
                "created": True,
            }

    def find_by_conversation_id(self, conversation_id: str) -> dict[str, Any] | None:
        """Return a stored record for tests and future delivery workers."""
        with self._connect() as connection:
            self._initialize(connection)
            row = connection.execute(
                "SELECT * FROM order_requests WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return dict(row) if row is not None else None
