from __future__ import annotations

from datetime import date, datetime
import json
from typing import Iterable

from database import DEFAULT_ESTADOS, get_connection


MONTHS_ES = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dic",
}


def get_estados() -> tuple[str, ...]:
    return DEFAULT_ESTADOS


def get_options(tipo: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT valor FROM opciones_dinamicas WHERE tipo = ? ORDER BY valor COLLATE NOCASE",
            (tipo,),
        ).fetchall()
    return [row["valor"] for row in rows]


def normalize_ticket_number(numero_ticket: str) -> str:
    return " ".join(numero_ticket.strip().split())


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _record_action(
    conn,
    action_type: str,
    ticket_id: int | None,
    before_data: dict[str, object] | list[dict[str, object]] | None,
    after_data: dict[str, object] | list[dict[str, object]] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO action_history (action_type, ticket_id, created_at, before_data, after_data)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            action_type,
            ticket_id,
            _now(),
            json.dumps(before_data) if before_data is not None else None,
            json.dumps(after_data) if after_data is not None else None,
        ),
    )


def _fetch_ticket(conn, ticket_id: int) -> dict[str, object] | None:
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else None


def _fetch_ticket_comments(conn, ticket_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM comentarios WHERE ticket_id = ? ORDER BY id ASC",
        (ticket_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_ticket_updates(conn, ticket_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM ticket_daily_updates WHERE ticket_id = ? ORDER BY id ASC",
        (ticket_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_ticket_status_changes(conn, ticket_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT * FROM ticket_daily_status_changes WHERE ticket_id = ? ORDER BY id ASC",
        (ticket_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _fetch_daily_update(conn, ticket_id: int, update_date: date) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT * FROM ticket_daily_updates WHERE ticket_id = ? AND fecha = ?",
        (ticket_id, update_date.isoformat()),
    ).fetchone()
    return dict(row) if row else None


def _fetch_daily_status_change(conn, ticket_id: int, change_date: date) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT * FROM ticket_daily_status_changes WHERE ticket_id = ? AND fecha = ?",
        (ticket_id, change_date.isoformat()),
    ).fetchone()
    return dict(row) if row else None


def _insert_ticket(conn, ticket: dict[str, object]) -> None:
    conn.execute(
        """
        INSERT INTO tickets (
            id, fecha_creacion, pais, numero_ticket, mail, phone, estado,
            problem_name, description, estado_actual
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticket["id"],
            ticket["fecha_creacion"],
            ticket["pais"],
            ticket.get("numero_ticket", ""),
            ticket.get("mail", ""),
            ticket.get("phone", ""),
            ticket["estado"],
            ticket.get("problem_name", ""),
            ticket.get("description", ""),
            ticket["estado_actual"],
        ),
    )


def _restore_ticket(conn, ticket: dict[str, object]) -> None:
    conn.execute("DELETE FROM tickets WHERE id = ?", (ticket["id"],))
    _insert_ticket(conn, ticket)


def _update_ticket_row(conn, ticket_id: int, ticket_data: dict[str, object]) -> None:
    conn.execute(
        """
        UPDATE tickets
        SET fecha_creacion = ?, pais = ?, numero_ticket = ?, mail = ?, phone = ?,
            estado = ?, problem_name = ?, description = ?, estado_actual = ?
        WHERE id = ?
        """,
        (
            ticket_data["fecha_creacion"],
            ticket_data["pais"],
            ticket_data.get("numero_ticket", ""),
            ticket_data.get("mail", ""),
            ticket_data.get("phone", ""),
            ticket_data["estado"],
            ticket_data.get("problem_name", ""),
            ticket_data.get("description", ""),
            ticket_data["estado_actual"],
            ticket_id,
        ),
    )


def _restore_daily_update(conn, before_update: dict[str, object] | None, ticket_id: int, update_date: str) -> None:
    conn.execute("DELETE FROM ticket_daily_updates WHERE ticket_id = ? AND fecha = ?", (ticket_id, update_date))
    if before_update:
        conn.execute(
            """
            INSERT INTO ticket_daily_updates (id, ticket_id, fecha, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (before_update["id"], before_update["ticket_id"], before_update["fecha"], before_update["updated_at"]),
        )


def _restore_daily_status_change(
    conn,
    before_change: dict[str, object] | None,
    ticket_id: int,
    change_date: str,
) -> None:
    conn.execute("DELETE FROM ticket_daily_status_changes WHERE ticket_id = ? AND fecha = ?", (ticket_id, change_date))
    if before_change:
        conn.execute(
            """
            INSERT INTO ticket_daily_status_changes (id, ticket_id, fecha, estado, changed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                before_change["id"],
                before_change["ticket_id"],
                before_change["fecha"],
                before_change["estado"],
                before_change["changed_at"],
            ),
        )


def _restore_daily_report_override(conn, before_override: dict[str, object] | None, report_date: str, ticket_id: int) -> None:
    conn.execute("DELETE FROM daily_report_ticket_overrides WHERE fecha = ? AND ticket_id = ?", (report_date, ticket_id))
    if before_override:
        conn.execute(
            """
            INSERT INTO daily_report_ticket_overrides (id, fecha, ticket_id, included, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                before_override["id"],
                before_override["fecha"],
                before_override["ticket_id"],
                before_override["included"],
                before_override["updated_at"],
            ),
        )


def _restore_daily_report_overrides(conn, before_overrides: list[dict[str, object]], report_date: str) -> None:
    conn.execute("DELETE FROM daily_report_ticket_overrides WHERE fecha = ?", (report_date,))
    for override in before_overrides:
        conn.execute(
            """
            INSERT INTO daily_report_ticket_overrides (id, fecha, ticket_id, included, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (override["id"], override["fecha"], override["ticket_id"], override["included"], override["updated_at"]),
        )


def _mark_ticket_updated_with_conn(conn, ticket_id: int, update_date: date) -> None:
    conn.execute(
        """
        INSERT INTO ticket_daily_updates (ticket_id, fecha, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(ticket_id, fecha) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (ticket_id, update_date.isoformat(), _now()),
    )


def _record_ticket_status_change(conn, ticket_id: int, estado: str, change_date: date | None) -> None:
    if change_date is None:
        return

    conn.execute(
        """
        INSERT INTO ticket_daily_status_changes (ticket_id, fecha, estado, changed_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ticket_id, fecha) DO UPDATE SET
            estado = excluded.estado,
            changed_at = excluded.changed_at
        """,
        (ticket_id, change_date.isoformat(), estado, _now()),
    )


def add_option(tipo: str, valor: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError("El valor no puede estar vacio.")

    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO opciones_dinamicas (tipo, valor) VALUES (?, ?)",
            (tipo, valor),
        )
    return valor


def create_ticket(ticket_data: dict[str, str]) -> int:
    required_fields = ("fecha_creacion", "pais", "estado", "estado_actual")
    missing = [field for field in required_fields if not ticket_data.get(field, "").strip()]
    if missing:
        raise ValueError("Completa los campos obligatorios: " + ", ".join(missing))

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tickets (
                fecha_creacion, pais, numero_ticket, mail, phone, estado,
                problem_name, description, estado_actual
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_data["fecha_creacion"],
                ticket_data["pais"].strip(),
                ticket_data.get("numero_ticket", "").strip(),
                ticket_data.get("mail", "").strip(),
                ticket_data.get("phone", "").strip(),
                ticket_data["estado"].strip(),
                ticket_data.get("problem_name", "").strip(),
                ticket_data.get("description", "").strip(),
                ticket_data["estado_actual"].strip(),
            ),
        )
        ticket_id = int(cursor.lastrowid)
        _record_action(conn, "create_ticket", ticket_id, None, _fetch_ticket(conn, ticket_id))
        return ticket_id


def ticket_exists(numero_ticket: str) -> bool:
    numero_ticket = normalize_ticket_number(numero_ticket)
    if not numero_ticket:
        return False

    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM tickets WHERE lower(numero_ticket) = lower(?) LIMIT 1",
            (numero_ticket,),
        ).fetchone()
    return row is not None


def get_all_tickets_for_inbound(report_date: date | None = None) -> list[dict[str, object]]:
    """Return tickets (with phone) for inbound call selection.
    If report_date is given, only tickets visible on that date."""
    with get_connection() as conn:
        if report_date:
            today_iso = date.today().isoformat()
            report_iso = report_date.isoformat()
            if report_iso == today_iso:
                rows = conn.execute(
                    """
                    SELECT id, numero_ticket, problem_name, phone
                    FROM tickets
                    WHERE numero_ticket != ''
                      AND (fecha_creacion = ?
                           OR (fecha_creacion < ? AND estado NOT IN ('cerrado', 'no tomado')))
                    ORDER BY fecha_creacion DESC, id DESC
                    """,
                    (today_iso, today_iso),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, numero_ticket, problem_name, phone
                    FROM tickets
                    WHERE numero_ticket != '' AND fecha_creacion = ?
                    ORDER BY fecha_creacion DESC, id DESC
                    """,
                    (report_iso,),
                ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, numero_ticket, problem_name, phone
                FROM tickets
                WHERE numero_ticket != ''
                ORDER BY fecha_creacion DESC, id DESC
                """,
            ).fetchall()
    return [dict(row) for row in rows]


def create_ticket_list(
    rows: list[dict[str, str]],
    defaults: dict[str, str],
) -> dict[str, object]:
    created: list[str] = []
    duplicates: list[str] = []
    ignored: list[int] = []
    seen_in_batch: set[str] = set()

    for index, row in enumerate(rows, start=1):
        numero_ticket = normalize_ticket_number(row.get("numero_ticket", ""))
        if not numero_ticket:
            ignored.append(index)
            continue

        duplicate_key = numero_ticket.lower()
        if duplicate_key in seen_in_batch or ticket_exists(numero_ticket):
            duplicates.append(numero_ticket)
            continue

        ticket_data = {
            **defaults,
            "numero_ticket": numero_ticket,
            "problem_name": row.get("problem_name", "").strip(),
        }
        create_ticket(ticket_data)
        seen_in_batch.add(duplicate_key)
        created.append(numero_ticket)

    return {
        "created": created,
        "duplicates": duplicates,
        "ignored": ignored,
    }


def get_ticket(ticket_id: int) -> dict[str, object] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return dict(row) if row else None


def update_ticket(
    ticket_id: int,
    ticket_data: dict[str, str],
    update_date: date | None = None,
    status_change_date: date | None = None,
) -> None:
    required_fields = ("fecha_creacion", "pais", "estado", "estado_actual")
    missing = [field for field in required_fields if not ticket_data.get(field, "").strip()]
    if missing:
        raise ValueError("Completa los campos obligatorios: " + ", ".join(missing))

    cleaned_data = {
        "fecha_creacion": ticket_data["fecha_creacion"].strip(),
        "pais": ticket_data["pais"].strip(),
        "numero_ticket": ticket_data.get("numero_ticket", "").strip(),
        "mail": ticket_data.get("mail", "").strip(),
        "phone": ticket_data.get("phone", "").strip(),
        "estado": ticket_data["estado"].strip(),
        "problem_name": ticket_data.get("problem_name", "").strip(),
        "description": ticket_data.get("description", "").strip(),
        "estado_actual": ticket_data["estado_actual"].strip(),
    }
    with get_connection() as conn:
        before = {
            "ticket": _fetch_ticket(conn, ticket_id),
            "daily_update": None,
            "update_date": None,
            "status_change": None,
            "status_change_date": None,
        }
        if before["ticket"] is None:
            return
        if update_date:
            before["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
            before["update_date"] = update_date.isoformat()
        if status_change_date:
            before["status_change"] = _fetch_daily_status_change(conn, ticket_id, status_change_date)
            before["status_change_date"] = status_change_date.isoformat()
        _update_ticket_row(conn, ticket_id, cleaned_data)
        if before["ticket"] and str(before["ticket"]["estado"]) != cleaned_data["estado"]:
            _record_ticket_status_change(conn, ticket_id, cleaned_data["estado"], status_change_date)
        if update_date:
            _mark_ticket_updated_with_conn(conn, ticket_id, update_date)
        after = {
            "ticket": _fetch_ticket(conn, ticket_id),
            "daily_update": None,
            "update_date": before["update_date"],
            "status_change": None,
            "status_change_date": before["status_change_date"],
        }
        if update_date:
            after["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
        if status_change_date:
            after["status_change"] = _fetch_daily_status_change(conn, ticket_id, status_change_date)
        _record_action(conn, "update_ticket", ticket_id, before, after)


def get_visible_tickets(selected_date: date) -> list[dict[str, object]]:
    selected_iso = selected_date.isoformat()
    today_iso = date.today().isoformat()

    with get_connection() as conn:
        if selected_iso == today_iso:
            rows = conn.execute(
                """
                SELECT
                    tickets.*,
                    fecha_creacion < ? AS is_rollover,
                    (
                        SELECT comentarios.comentario
                        FROM comentarios
                        WHERE comentarios.ticket_id = tickets.id
                        ORDER BY comentarios.fecha_hora DESC, comentarios.id DESC
                        LIMIT 1
                    ) AS last_comment,
                    (
                        SELECT COUNT(*)
                        FROM comentarios
                        WHERE comentarios.ticket_id = tickets.id
                    ) AS comment_count
                FROM tickets
                LEFT JOIN ticket_daily_status_changes
                  ON ticket_daily_status_changes.ticket_id = tickets.id
                 AND ticket_daily_status_changes.fecha = ?
                WHERE fecha_creacion = ?
                   OR (fecha_creacion < ? AND tickets.estado IN ('respondido', 'pendiente', 'critico'))
                   OR ticket_daily_status_changes.estado IN ('cerrado', 'no tomado')
                ORDER BY is_rollover ASC, fecha_creacion DESC, tickets.id DESC
                """,
                (today_iso, selected_iso, today_iso, today_iso),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    tickets.*,
                    0 AS is_rollover,
                    (
                        SELECT comentarios.comentario
                        FROM comentarios
                        WHERE comentarios.ticket_id = tickets.id
                        ORDER BY comentarios.fecha_hora DESC, comentarios.id DESC
                        LIMIT 1
                    ) AS last_comment,
                    (
                        SELECT COUNT(*)
                        FROM comentarios
                        WHERE comentarios.ticket_id = tickets.id
                    ) AS comment_count
                FROM tickets
                LEFT JOIN ticket_daily_status_changes
                  ON ticket_daily_status_changes.ticket_id = tickets.id
                 AND ticket_daily_status_changes.fecha = ?
                WHERE fecha_creacion = ?
                   OR ticket_daily_status_changes.estado IN ('cerrado', 'no tomado')
                ORDER BY tickets.id DESC
                """,
                (selected_iso, selected_iso),
            ).fetchall()

    return [dict(row) for row in rows]


def delete_ticket(ticket_id: int) -> None:
    with get_connection() as conn:
        before = {
            "ticket": _fetch_ticket(conn, ticket_id),
            "comments": _fetch_ticket_comments(conn, ticket_id),
            "daily_updates": _fetch_ticket_updates(conn, ticket_id),
            "status_changes": _fetch_ticket_status_changes(conn, ticket_id),
        }
        if before["ticket"] is None:
            return
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        _record_action(conn, "delete_ticket", ticket_id, before, None)


def delete_tickets(ticket_ids: list[int]) -> None:
    if not ticket_ids:
        return

    placeholders = ",".join("?" for _ in ticket_ids)
    with get_connection() as conn:
        before = [
            {
                "ticket": _fetch_ticket(conn, ticket_id),
                "comments": _fetch_ticket_comments(conn, ticket_id),
                "daily_updates": _fetch_ticket_updates(conn, ticket_id),
                "status_changes": _fetch_ticket_status_changes(conn, ticket_id),
            }
            for ticket_id in ticket_ids
            if _fetch_ticket(conn, ticket_id) is not None
        ]
        if not before:
            return
        conn.execute(f"DELETE FROM tickets WHERE id IN ({placeholders})", ticket_ids)
        _record_action(conn, "delete_tickets", None, before, None)


def mark_ticket_updated(ticket_id: int, update_date: date, record_action: bool = True) -> None:
    with get_connection() as conn:
        before = _fetch_daily_update(conn, ticket_id, update_date)
        _mark_ticket_updated_with_conn(conn, ticket_id, update_date)
        after = _fetch_daily_update(conn, ticket_id, update_date)
        if record_action:
            _record_action(
                conn,
                "mark_updated",
                ticket_id,
                {"daily_update": before, "update_date": update_date.isoformat()},
                {"daily_update": after, "update_date": update_date.isoformat()},
            )


def unmark_ticket_updated(ticket_id: int, update_date: date) -> None:
    with get_connection() as conn:
        before = _fetch_daily_update(conn, ticket_id, update_date)
        if before is None:
            return

        conn.execute(
            "DELETE FROM ticket_daily_updates WHERE ticket_id = ? AND fecha = ?",
            (ticket_id, update_date.isoformat()),
        )
        _record_action(
            conn,
            "unmark_updated",
            ticket_id,
            {"daily_update": before, "update_date": update_date.isoformat()},
            {"daily_update": None, "update_date": update_date.isoformat()},
        )


def get_updated_ticket_ids(ticket_ids: list[int], update_date: date) -> set[int]:
    if not ticket_ids:
        return set()

    placeholders = ",".join("?" for _ in ticket_ids)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT ticket_id
            FROM ticket_daily_updates
            WHERE fecha = ?
              AND ticket_id IN ({placeholders})
            """,
            [update_date.isoformat(), *ticket_ids],
        ).fetchall()
    return {int(row["ticket_id"]) for row in rows}


DAILY_REPORT_FIELDS = (
    "new_tickets_count",
    "inbound_calls",
    "outbound_calls",
    "missed_calls",
    "moor_chat",
    "goto_chat",
    "emails",
    "tickets_hq_help",
    "open_tickets_count",
)


def get_daily_report(report_date: date) -> dict[str, int]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_reports WHERE fecha = ?",
            (report_date.isoformat(),),
        ).fetchone()

    if not row:
        return {field: 0 for field in DAILY_REPORT_FIELDS}
    return {field: int(row[field] or 0) for field in DAILY_REPORT_FIELDS}


def save_daily_report(report_date: date, data: dict[str, int]) -> None:
    values = {field: max(0, int(data.get(field, 0))) for field in DAILY_REPORT_FIELDS}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_reports (
                fecha, inbound_calls, outbound_calls, missed_calls, moor_chat,
                goto_chat, emails, tickets_hq_help, new_tickets_count, open_tickets_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fecha) DO UPDATE SET
                inbound_calls = excluded.inbound_calls,
                outbound_calls = excluded.outbound_calls,
                missed_calls = excluded.missed_calls,
                moor_chat = excluded.moor_chat,
                goto_chat = excluded.goto_chat,
                emails = excluded.emails,
                tickets_hq_help = excluded.tickets_hq_help,
                new_tickets_count = excluded.new_tickets_count,
                open_tickets_count = excluded.open_tickets_count,
                updated_at = excluded.updated_at
            """,
            (
                report_date.isoformat(),
                values["inbound_calls"],
                values["outbound_calls"],
                values["missed_calls"],
                values["moor_chat"],
                values["goto_chat"],
                values["emails"],
                values["tickets_hq_help"],
                values["new_tickets_count"],
                values["open_tickets_count"],
                now,
            ),
        )


def add_inbound_call(report_date: date, phone: str, ticket_number: str) -> dict[str, object]:
    """Add an inbound call record with phone and ticket number for a given date."""
    phone = phone.strip()
    ticket_number = ticket_number.strip()
    if not phone or not ticket_number:
        raise ValueError("Phone and ticket number are required.")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO inbound_call_details (fecha, phone, numero_ticket, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (report_date.isoformat(), phone, ticket_number, _now()),
        )
        row = conn.execute(
            "SELECT * FROM inbound_call_details WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def get_inbound_call_details(report_date: date) -> list[dict[str, object]]:
    """Get all inbound call records for a given date."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM inbound_call_details WHERE fecha = ? ORDER BY id ASC",
            (report_date.isoformat(),),
        ).fetchall()
    return [dict(row) for row in rows]


def remove_inbound_call(call_id: int) -> None:
    """Remove an inbound call record by its id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM inbound_call_details WHERE id = ?", (call_id,))


def get_hq_ticket_ids(report_date: date) -> set[int]:
    """Get set of ticket ids selected for HQ help on a given date."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticket_id FROM daily_report_hq_tickets WHERE fecha = ?",
            (report_date.isoformat(),),
        ).fetchall()
    return {int(row["ticket_id"]) for row in rows}


def set_hq_ticket(report_date: date, ticket_id: int, included: bool) -> None:
    """Add or remove a ticket from the HQ help list for a given date."""
    with get_connection() as conn:
        if included:
            conn.execute(
                """
                INSERT OR IGNORE INTO daily_report_hq_tickets (fecha, ticket_id, updated_at)
                VALUES (?, ?, ?)
                """,
                (report_date.isoformat(), ticket_id, _now()),
            )
        else:
            conn.execute(
                "DELETE FROM daily_report_hq_tickets WHERE fecha = ? AND ticket_id = ?",
                (report_date.isoformat(), ticket_id),
            )


def get_excluded_ticket_ids(report_date: date, list_type: str) -> set[int]:
    """Get set of ticket ids excluded from a list (new|open) on a given date."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticket_id FROM daily_report_ticket_exclusions WHERE fecha = ? AND list_type = ?",
            (report_date.isoformat(), list_type),
        ).fetchall()
    return {int(row["ticket_id"]) for row in rows}


def set_ticket_exclusion(report_date: date, ticket_id: int, list_type: str, excluded: bool) -> None:
    """Add or remove a ticket exclusion from a list (new|open) for a given date."""
    with get_connection() as conn:
        if excluded:
            conn.execute(
                """
                INSERT OR IGNORE INTO daily_report_ticket_exclusions (fecha, ticket_id, list_type, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (report_date.isoformat(), ticket_id, list_type, _now()),
            )
        else:
            conn.execute(
                "DELETE FROM daily_report_ticket_exclusions WHERE fecha = ? AND ticket_id = ? AND list_type = ?",
                (report_date.isoformat(), ticket_id, list_type),
            )


def auto_calc_new_tickets(report_date: date) -> list[dict[str, object]]:
    """Get tickets created on the given date (excluding 'no tomado' and exclusions)."""
    excluded = get_excluded_ticket_ids(report_date, "new")
    with get_connection() as conn:
        query = """
            SELECT id, numero_ticket, problem_name
            FROM tickets
            WHERE fecha_creacion = ?
              AND estado != 'no tomado'
        """
        params: list[object] = [report_date.isoformat()]
        if excluded:
            placeholders = ",".join("?" for _ in excluded)
            query += f" AND id NOT IN ({placeholders})"
            params.extend(excluded)
        query += " ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_tickets_for_list(report_date: date, list_type: str) -> list[dict[str, object]]:
    """Get all eligible tickets for a list (new|open) without exclusion filter."""
    with get_connection() as conn:
        if list_type == "new":
            rows = conn.execute(
                """
                SELECT id, numero_ticket, problem_name, estado
                FROM tickets
                WHERE fecha_creacion = ?
                  AND estado != 'no tomado'
                ORDER BY id DESC
                """,
                (report_date.isoformat(),),
            ).fetchall()
        elif list_type == "open":
            rows = conn.execute(
                """
                SELECT id, numero_ticket, problem_name, estado
                FROM tickets
                WHERE fecha_creacion <= ?
                  AND estado NOT IN ('cerrado', 'no tomado')
                ORDER BY fecha_creacion DESC, id DESC
                """,
                (report_date.isoformat(),),
            ).fetchall()
        else:
            return []
    return [dict(row) for row in rows]


def auto_calc_open_tickets(report_date: date) -> list[dict[str, object]]:
    """Get tickets that are open at end of day (excl. cerrado/no tomado and exclusions)."""
    excluded = get_excluded_ticket_ids(report_date, "open")
    with get_connection() as conn:
        query = """
            SELECT id, numero_ticket, problem_name, estado_actual
            FROM tickets
            WHERE fecha_creacion <= ?
              AND estado NOT IN ('cerrado', 'no tomado')
        """
        params: list[object] = [report_date.isoformat()]
        if excluded:
            placeholders = ",".join("?" for _ in excluded)
            query += f" AND id NOT IN ({placeholders})"
            params.extend(excluded)
        query += " ORDER BY fecha_creacion DESC, id DESC"
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _fetch_daily_report_override(conn, report_date: date, ticket_id: int) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT *
        FROM daily_report_ticket_overrides
        WHERE fecha = ? AND ticket_id = ?
        """,
        (report_date.isoformat(), ticket_id),
    ).fetchone()
    return dict(row) if row else None


def _daily_report_origin(created_today: bool, updated_today: bool, closed_today: bool, included: bool, automatic: bool) -> str:
    if closed_today:
        return "Cerrado hoy"
    if created_today and updated_today:
        return "Creado y actualizado"
    if created_today:
        return "Creado hoy"
    if updated_today:
        return "Actualizado hoy"
    if included and not automatic:
        return "Manual"
    return "Fuera de regla"


def get_daily_report_ticket_details(report_date: date) -> list[dict[str, object]]:
    report_iso = report_date.isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                tickets.*,
                ticket_daily_updates.ticket_id IS NOT NULL AS updated_today,
                ticket_daily_status_changes.estado AS status_changed_today,
                daily_report_ticket_overrides.included AS override_included
            FROM tickets
            LEFT JOIN ticket_daily_updates
              ON ticket_daily_updates.ticket_id = tickets.id
             AND ticket_daily_updates.fecha = ?
            LEFT JOIN ticket_daily_status_changes
              ON ticket_daily_status_changes.ticket_id = tickets.id
             AND ticket_daily_status_changes.fecha = ?
            LEFT JOIN daily_report_ticket_overrides
              ON daily_report_ticket_overrides.ticket_id = tickets.id
             AND daily_report_ticket_overrides.fecha = ?
            ORDER BY tickets.fecha_creacion DESC, tickets.id DESC
            """,
            (report_iso, report_iso, report_iso),
        ).fetchall()

    details: list[dict[str, object]] = []
    for row in rows:
        ticket = dict(row)
        created_today = str(ticket["fecha_creacion"]) == report_iso
        updated_today = bool(ticket["updated_today"])
        closed_today = str(ticket.get("status_changed_today") or "").lower() in {"cerrado", "no tomado"}
        automatic = created_today or updated_today or closed_today
        override = ticket["override_included"]
        included = automatic if override is None else bool(override)
        details.append(
            {
                **ticket,
                "automatic": automatic,
                "included": included,
                "origin": _daily_report_origin(created_today, updated_today, closed_today, included, automatic),
            }
        )

    details.sort(
        key=lambda ticket: (
            bool(ticket["included"]),
            bool(ticket["automatic"]),
            str(ticket["fecha_creacion"]),
            int(ticket["id"]),
        ),
        reverse=True,
    )
    return details


def count_daily_report_tickets(report_date: date) -> int:
    return sum(1 for ticket in get_daily_report_ticket_details(report_date) if ticket["included"])


def set_daily_report_ticket_included(report_date: date, ticket_id: int, included: bool) -> None:
    with get_connection() as conn:
        before = _fetch_daily_report_override(conn, report_date, ticket_id)
        conn.execute(
            """
            INSERT INTO daily_report_ticket_overrides (fecha, ticket_id, included, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(fecha, ticket_id) DO UPDATE SET
                included = excluded.included,
                updated_at = excluded.updated_at
            """,
            (report_date.isoformat(), ticket_id, 1 if included else 0, _now()),
        )
        after = _fetch_daily_report_override(conn, report_date, ticket_id)
        _record_action(
            conn,
            "daily_report_ticket_override",
            ticket_id,
            {"override": before, "report_date": report_date.isoformat()},
            {"override": after, "report_date": report_date.isoformat()},
        )


def reset_daily_report_ticket_overrides(report_date: date) -> None:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_report_ticket_overrides WHERE fecha = ? ORDER BY id ASC",
            (report_date.isoformat(),),
        ).fetchall()
        before = [dict(row) for row in rows]
        if not before:
            return

        conn.execute("DELETE FROM daily_report_ticket_overrides WHERE fecha = ?", (report_date.isoformat(),))
        _record_action(
            conn,
            "daily_report_reset_overrides",
            None,
            {"overrides": before, "report_date": report_date.isoformat()},
            {"overrides": [], "report_date": report_date.isoformat()},
        )


def _format_ticket_list(tickets: list[dict[str, object]]) -> str:
    """Format a list of tickets inline: count → ticket1, ticket2."""
    if not tickets:
        return "0"
    parts = [str(t["numero_ticket"]) for t in tickets if t.get("numero_ticket")]
    return f"{len(tickets)} — {', '.join(parts)}"


def _format_inbound_list(details: list[dict[str, object]]) -> str:
    """Format inbound calls inline: count → (phone + ticket), ..."""
    if not details:
        return "0"
    parts = [f"({d['phone']} + {d['numero_ticket']})" for d in details]
    return f"{len(details)} — {', '.join(parts)}"


def _format_open_tickets(tickets: list[dict[str, object]]) -> str:
    """Format open tickets: count then one ticket per line."""
    if not tickets:
        return "0"
    lines = [str(len(tickets))]
    for t in tickets:
        issue = t.get("problem_name") or ""
        lines.append(f"{t['numero_ticket']} : {issue}")
    return "\n".join(lines)


def build_daily_report_message(
    report_date: date,
    data: dict[str, int],
    inbound_details: list[dict[str, object]] | None = None,
    hq_ticket_numbers: list[str] | None = None,
    new_tickets: list[dict[str, object]] | None = None,
    open_tickets: list[dict[str, object]] | None = None,
) -> str:
    formatted_date = f"{report_date.month:02d}/{report_date.day:02d}/{report_date.year % 100}"
    values = {field: int(data.get(field, 0)) for field in DAILY_REPORT_FIELDS}

    lines = [f"Daily Work Report: {formatted_date}"]
    lines.append(f"● New Tickets: {_format_ticket_list(new_tickets) if new_tickets else values['new_tickets_count']}")
    lines.append(f"● Inbound calls: {_format_inbound_list(inbound_details) if inbound_details else values['inbound_calls']}")
    lines.append(f"● Outbound calls: {values['outbound_calls']}")
    lines.append(f"● Missed calls: {values['missed_calls']}")
    lines.append(f"● 7 moor platform online chats: {values['moor_chat']}")
    lines.append(f"● GoTo platform online chats: {values['goto_chat']}")
    lines.append(f"● Emails: {values['emails']}")
    lines.append(f"● Tickets needing HQ help or attention: {', '.join(hq_ticket_numbers) if hq_ticket_numbers else values['tickets_hq_help']}")
    lines.append(f"● Open tickets: {_format_open_tickets(open_tickets) if open_tickets else values['open_tickets_count']}")

    return "\n".join(lines)


def update_ticket_estado(
    ticket_id: int,
    estado: str,
    update_date: date | None = None,
    status_change_date: date | None = None,
) -> None:
    estado = estado.strip()
    if estado not in DEFAULT_ESTADOS:
        raise ValueError("Estado invalido.")

    with get_connection() as conn:
        before = {
            "ticket": _fetch_ticket(conn, ticket_id),
            "daily_update": None,
            "update_date": None,
            "status_change": None,
            "status_change_date": None,
        }
        if before["ticket"] is None:
            return
        if update_date:
            before["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
            before["update_date"] = update_date.isoformat()
        if status_change_date:
            before["status_change"] = _fetch_daily_status_change(conn, ticket_id, status_change_date)
            before["status_change_date"] = status_change_date.isoformat()
        conn.execute("UPDATE tickets SET estado = ? WHERE id = ?", (estado, ticket_id))
        if before["ticket"] and str(before["ticket"]["estado"]) != estado:
            _record_ticket_status_change(conn, ticket_id, estado, status_change_date)
        if update_date:
            _mark_ticket_updated_with_conn(conn, ticket_id, update_date)
        after = {
            "ticket": _fetch_ticket(conn, ticket_id),
            "daily_update": None,
            "update_date": before["update_date"],
            "status_change": None,
            "status_change_date": before["status_change_date"],
        }
        if update_date:
            after["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
        if status_change_date:
            after["status_change"] = _fetch_daily_status_change(conn, ticket_id, status_change_date)
        _record_action(conn, "update_estado", ticket_id, before, after)


def update_ticket_estado_actual(ticket_id: int, estado_actual: str, update_date: date | None = None) -> None:
    estado_actual = estado_actual.strip()
    if not estado_actual:
        raise ValueError("Estado actual invalido.")

    with get_connection() as conn:
        before = {"ticket": _fetch_ticket(conn, ticket_id), "daily_update": None, "update_date": None}
        if before["ticket"] is None:
            return
        if update_date:
            before["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
            before["update_date"] = update_date.isoformat()
        conn.execute(
            "UPDATE tickets SET estado_actual = ? WHERE id = ?",
            (estado_actual, ticket_id),
        )
        if update_date:
            _mark_ticket_updated_with_conn(conn, ticket_id, update_date)
        after = {"ticket": _fetch_ticket(conn, ticket_id), "daily_update": None, "update_date": before["update_date"]}
        if update_date:
            after["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
        _record_action(conn, "update_estado_actual", ticket_id, before, after)


def get_comments(ticket_id: int) -> list[dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT fecha_hora, comentario
            FROM comentarios
            WHERE ticket_id = ?
            ORDER BY fecha_hora ASC, id ASC
            """,
            (ticket_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_comment(ticket_id: int, comentario: str, update_date: date | None = None) -> None:
    comentario = comentario.strip()
    if not comentario:
        raise ValueError("El comentario no puede estar vacio.")

    with get_connection() as conn:
        before = {"daily_update": None, "update_date": None}
        if update_date:
            before["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
            before["update_date"] = update_date.isoformat()
        cursor = conn.execute(
            "INSERT INTO comentarios (ticket_id, fecha_hora, comentario) VALUES (?, ?, ?)",
            (ticket_id, _now(), comentario),
        )
        comment_id = int(cursor.lastrowid)
        if update_date:
            _mark_ticket_updated_with_conn(conn, ticket_id, update_date)
        comment = dict(conn.execute("SELECT * FROM comentarios WHERE id = ?", (comment_id,)).fetchone())
        after = {"comment": comment, "daily_update": None, "update_date": before["update_date"]}
        if update_date:
            after["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
        _record_action(conn, "add_comment", ticket_id, before, after)


def _restore_deleted_ticket_payload(conn, payload: dict[str, object]) -> None:
    ticket = payload.get("ticket")
    if not isinstance(ticket, dict):
        return

    _restore_ticket(conn, ticket)
    for comment in payload.get("comments", []):
        conn.execute(
            """
            INSERT INTO comentarios (id, ticket_id, fecha_hora, comentario)
            VALUES (?, ?, ?, ?)
            """,
            (comment["id"], comment["ticket_id"], comment["fecha_hora"], comment["comentario"]),
        )
    for update in payload.get("daily_updates", []):
        conn.execute(
            """
            INSERT INTO ticket_daily_updates (id, ticket_id, fecha, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (update["id"], update["ticket_id"], update["fecha"], update["updated_at"]),
        )
    for status_change in payload.get("status_changes", []):
        conn.execute(
            """
            INSERT INTO ticket_daily_status_changes (id, ticket_id, fecha, estado, changed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                status_change["id"],
                status_change["ticket_id"],
                status_change["fecha"],
                status_change["estado"],
                status_change["changed_at"],
            ),
        )


def _restore_ticket_action(conn, before: dict[str, object]) -> None:
    ticket = before.get("ticket")
    if isinstance(ticket, dict):
        if _fetch_ticket(conn, int(ticket["id"])) is None:
            _insert_ticket(conn, ticket)
        else:
            _update_ticket_row(conn, int(ticket["id"]), ticket)

    update_date = before.get("update_date")
    if ticket and update_date:
        _restore_daily_update(conn, before.get("daily_update"), int(ticket["id"]), str(update_date))

    status_change_date = before.get("status_change_date")
    if ticket and status_change_date:
        _restore_daily_status_change(conn, before.get("status_change"), int(ticket["id"]), str(status_change_date))


def _revert_action_by_row(conn, action: dict[str, object]) -> str:
    """Revert a single action (dict from action_history row) and return description."""
    action_type = str(action["action_type"])
    ticket_id = action["ticket_id"]
    before = json.loads(action["before_data"]) if action["before_data"] else None
    after = json.loads(action["after_data"]) if action["after_data"] else None

    if action_type == "create_ticket" and after:
        conn.execute("DELETE FROM tickets WHERE id = ?", (after["id"],))
        description = "Creacion de ticket revertida."
    elif action_type == "delete_ticket" and before:
        _restore_deleted_ticket_payload(conn, before)
        description = "Eliminacion de ticket revertida."
    elif action_type == "delete_tickets" and isinstance(before, list):
        for payload in before:
            _restore_deleted_ticket_payload(conn, payload)
        description = "Eliminacion multiple revertida."
    elif action_type in {"update_ticket", "update_estado", "update_estado_actual"} and before:
        _restore_ticket_action(conn, before)
        description = "Cambio de ticket revertido."
    elif action_type == "add_comment" and after:
        comment = after.get("comment")
        if isinstance(comment, dict):
            conn.execute("DELETE FROM comentarios WHERE id = ?", (comment["id"],))
        if ticket_id and before and before.get("update_date"):
            _restore_daily_update(conn, before.get("daily_update"), int(ticket_id), str(before["update_date"]))
        description = "Comentario revertido."
    elif action_type in {"mark_updated", "unmark_updated"} and ticket_id and before:
        _restore_daily_update(conn, before.get("daily_update"), int(ticket_id), str(before["update_date"]))
        description = "Marca de actualizado revertida."
    elif action_type == "daily_report_ticket_override" and ticket_id and before:
        _restore_daily_report_override(conn, before.get("override"), str(before["report_date"]), int(ticket_id))
        description = "Seleccion de ticket del reporte revertida."
    elif action_type == "daily_report_reset_overrides" and before:
        _restore_daily_report_overrides(conn, before.get("overrides", []), str(before["report_date"]))
        description = "Seleccion del reporte restaurada."
    else:
        raise ValueError("No se pudo revertir esta accion.")

    conn.execute("UPDATE action_history SET undone = 1 WHERE id = ?", (action["id"],))
    return description


def revert_last_action() -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM action_history
            WHERE undone = 0
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        return _revert_action_by_row(conn, dict(row))


def revert_action(action_id: int) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM action_history WHERE id = ? AND undone = 0",
            (action_id,),
        ).fetchone()
        if not row:
            raise ValueError("Accion no encontrada o ya fue revertida.")
        return _revert_action_by_row(conn, dict(row))


ACTION_LABELS = {
    "create_ticket": "Creo ticket",
    "update_ticket": "Edito ticket",
    "delete_ticket": "Elimino ticket",
    "delete_tickets": "Elimino varios tickets",
    "update_estado": "Cambio estado",
    "update_estado_actual": "Cambio estado actual",
    "add_comment": "Agrego comentario",
    "mark_updated": "Marco actualizado",
    "unmark_updated": "Marco no actualizado",
    "daily_report_ticket_override": "Ajusto ticket de reporte",
    "daily_report_reset_overrides": "Restauro reporte automatico",
}


def _extract_ticket_number_from_payload(payload: object) -> str:
    if isinstance(payload, dict):
        ticket = payload.get("ticket") if "ticket" in payload else payload
        if isinstance(ticket, dict) and ticket.get("numero_ticket"):
            return str(ticket["numero_ticket"])
        comment = payload.get("comment")
        if isinstance(comment, dict) and comment.get("ticket_id"):
            return f"ID {comment['ticket_id']}"
    if isinstance(payload, list):
        tickets = [
            str(item["ticket"]["numero_ticket"])
            for item in payload
            if isinstance(item, dict)
            and isinstance(item.get("ticket"), dict)
            and item["ticket"].get("numero_ticket")
        ]
        if tickets:
            return ", ".join(tickets[:3]) + ("..." if len(tickets) > 3 else "")
    return ""


def get_action_history(limit: int = 80) -> list[dict[str, object]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT action_history.*, tickets.numero_ticket AS current_ticket
            FROM action_history
            LEFT JOIN tickets ON tickets.id = action_history.ticket_id
            ORDER BY action_history.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    history: list[dict[str, object]] = []
    for row in rows:
        action = dict(row)
        before = json.loads(action["before_data"]) if action["before_data"] else None
        after = json.loads(action["after_data"]) if action["after_data"] else None
        ticket_number = action.get("current_ticket") or _extract_ticket_number_from_payload(after) or _extract_ticket_number_from_payload(before) or "-"
        history.append(
            {
                "id": action["id"],
                "created_at": action["created_at"],
                "action": ACTION_LABELS.get(str(action["action_type"]), str(action["action_type"])),
                "ticket": ticket_number,
                "undone": bool(action["undone"]),
            }
        )
    return history


def build_sms_report(visible_tickets: Iterable[dict[str, object]], report_date: date) -> str:
    open_tickets = [
        ticket
        for ticket in visible_tickets
        if str(ticket["estado"]).lower() not in {"cerrado", "no tomado"}
    ]
    if not open_tickets:
        return ""

    formatted_date = f"{report_date.day} {MONTHS_ES[report_date.month]} {report_date.year}"
    lines = [f"Hi, daily open ticket report: {formatted_date}", ""]
    lines.extend(
        f"{ticket['numero_ticket']} : {ticket['problem_name']} : {ticket['estado_actual']}"
        for ticket in open_tickets
    )
    return "\n".join(lines)
