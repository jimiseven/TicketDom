from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tickets_data.db"

DEFAULT_ESTADOS = ("respondido", "pendiente", "cerrado", "no tomado", "critico")
DEFAULT_ESTADOS_ACTUALES = (
    "Awaiting hq team response",
    "Awaiting customer response",
)
DEFAULT_PAISES = ("United States",)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection configured for row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    """Create application tables and insert default dynamic options if needed."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_creacion DATE NOT NULL,
                pais TEXT NOT NULL,
                numero_ticket TEXT NOT NULL,
                mail TEXT,
                phone TEXT,
                estado TEXT NOT NULL,
                problem_name TEXT NOT NULL,
                description TEXT,
                estado_actual TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comentarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                fecha_hora DATETIME NOT NULL,
                comentario TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS opciones_dinamicas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL CHECK (tipo IN ('pais', 'estado_actual')),
                valor TEXT NOT NULL,
                UNIQUE(tipo, valor)
            );
            """
        )
        _run_migrations(conn)
        _insert_default_options(conn)


def _run_migrations(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()}
    if "phone" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN phone TEXT")


def _insert_default_options(conn: sqlite3.Connection) -> None:
    for pais in DEFAULT_PAISES:
        conn.execute(
            "INSERT OR IGNORE INTO opciones_dinamicas (tipo, valor) VALUES (?, ?)",
            ("pais", pais),
        )

    for estado_actual in DEFAULT_ESTADOS_ACTUALES:
        conn.execute(
            "INSERT OR IGNORE INTO opciones_dinamicas (tipo, valor) VALUES (?, ?)",
            ("estado_actual", estado_actual),
        )
