"""PostgreSQL-backed repository for email records."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.types.json import Json


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    gmail_id TEXT UNIQUE NOT NULL,
    subject TEXT,
    sender TEXT,
    recipients TEXT,
    snippet TEXT,
    body TEXT,
    has_attachments BOOLEAN DEFAULT FALSE,
    date TIMESTAMPTZ,
    is_starred BOOLEAN DEFAULT FALSE,
    labels TEXT[],
    analysis JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class EmailRepository:
    """Thin wrapper around psycopg for storing analysed emails."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn: Optional[psycopg.extensions.connection] = None

    def connect(self) -> psycopg.extensions.connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.database_url)
        return self._conn

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()

    @contextmanager
    def cursor(self):
        conn = self.connect()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def init_schema(self) -> None:
        with self.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)

    def upsert_email(
        self,
        *,
        gmail_id: str,
        subject: Optional[str],
        sender: Optional[str],
        recipients: List[str],
        snippet: Optional[str],
        body: Optional[str],
        has_attachments: bool,
        date: Optional[datetime],
        is_starred: bool,
        labels: List[str],
        analysis: Optional[Dict[str, Any]],
    ) -> int:
        recipients_value = ", ".join(recipients) if recipients else None
        labels_value = labels if labels else None

        with self.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO emails (
                    gmail_id, subject, sender, recipients, snippet, body,
                    has_attachments, date, is_starred, labels, analysis
                ) VALUES (
                    %(gmail_id)s, %(subject)s, %(sender)s, %(recipients)s, %(snippet)s,
                    %(body)s, %(has_attachments)s, %(date)s, %(is_starred)s, %(labels)s, %(analysis)s
                )
                ON CONFLICT (gmail_id) DO UPDATE SET
                    subject = EXCLUDED.subject,
                    sender = EXCLUDED.sender,
                    recipients = EXCLUDED.recipients,
                    snippet = EXCLUDED.snippet,
                    body = EXCLUDED.body,
                    has_attachments = EXCLUDED.has_attachments,
                    date = EXCLUDED.date,
                    is_starred = EXCLUDED.is_starred,
                    labels = EXCLUDED.labels,
                    analysis = EXCLUDED.analysis
                RETURNING id
                """,
                {
                    "gmail_id": gmail_id,
                    "subject": subject,
                    "sender": sender,
                    "recipients": recipients_value,
                    "snippet": snippet,
                    "body": body,
                    "has_attachments": has_attachments,
                    "date": date,
                    "is_starred": is_starred,
                    "labels": labels_value,
                    "analysis": Json(analysis) if analysis else None,
                },
            )

            record_id = cursor.fetchone()[0]

        return record_id

    def get_email(self, gmail_id: str) -> Optional[Dict[str, Any]]:
        with self.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, gmail_id, subject, sender, recipients, snippet, body,
                       has_attachments, date, is_starred, labels, analysis, created_at
                FROM emails
                WHERE gmail_id = %s
                """,
                (gmail_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_dict(row)

    def list_emails(self, *, limit: int, offset: int = 0) -> List[Dict[str, Any]]:
        with self.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, gmail_id, subject, sender, recipients, snippet, body,
                       has_attachments, date, is_starred, labels, analysis, created_at
                FROM emails
                ORDER BY date DESC NULLS LAST, created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def delete_email(self, gmail_id: str) -> bool:
        with self.cursor() as cursor:
            cursor.execute("DELETE FROM emails WHERE gmail_id = %s", (gmail_id,))
            return cursor.rowcount > 0

    def _row_to_dict(self, row) -> Dict[str, Any]:
        (
            record_id,
            gmail_id,
            subject,
            sender,
            recipients,
            snippet,
            body,
            has_attachments,
            date,
            is_starred,
            labels,
            analysis,
            created_at,
        ) = row

        recipients_list = [item.strip() for item in recipients.split(",")] if recipients else []
        labels_list = list(labels) if labels else []

        return {
            "id": record_id,
            "gmail_id": gmail_id,
            "subject": subject,
            "sender": sender,
            "recipients": recipients_list,
            "snippet": snippet,
            "body": body,
            "has_attachments": has_attachments,
            "date": date,
            "is_starred": is_starred,
            "labels": labels_list,
            "analysis": analysis,
            "created_at": created_at,
        }

    def __del__(self) -> None:  # pragma: no cover - defensive cleanup
        self.close()
