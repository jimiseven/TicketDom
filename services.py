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


def _fetch_daily_update(conn, ticket_id: int, update_date: date) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT * FROM ticket_daily_updates WHERE ticket_id = ? AND fecha = ?",
        (ticket_id, update_date.isoformat()),
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


def _mark_ticket_updated_with_conn(conn, ticket_id: int, update_date: date) -> None:
    conn.execute(
        """
        INSERT INTO ticket_daily_updates (ticket_id, fecha, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(ticket_id, fecha) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (ticket_id, update_date.isoformat(), _now()),
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


def update_ticket(ticket_id: int, ticket_data: dict[str, str], update_date: date | None = None) -> None:
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
        before = {"ticket": _fetch_ticket(conn, ticket_id), "daily_update": None, "update_date": None}
        if before["ticket"] is None:
            return
        if update_date:
            before["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
            before["update_date"] = update_date.isoformat()
        _update_ticket_row(conn, ticket_id, cleaned_data)
        if update_date:
            _mark_ticket_updated_with_conn(conn, ticket_id, update_date)
        after = {"ticket": _fetch_ticket(conn, ticket_id), "daily_update": None, "update_date": before["update_date"]}
        if update_date:
            after["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
        _record_action(conn, "update_ticket", ticket_id, before, after)


def get_visible_tickets(selected_date: date) -> list[dict[str, object]]:
    selected_iso = selected_date.isoformat()
    today_iso = date.today().isoformat()

    with get_connection() as conn:
        if selected_iso == today_iso:
            rows = conn.execute(
                """
                SELECT *, fecha_creacion < ? AS is_rollover
                FROM tickets
                WHERE fecha_creacion = ?
                   OR (fecha_creacion < ? AND estado IN ('respondido', 'pendiente', 'critico'))
                ORDER BY is_rollover ASC, fecha_creacion DESC, id DESC
                """,
                (today_iso, today_iso, today_iso),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *, 0 AS is_rollover
                FROM tickets
                WHERE fecha_creacion = ?
                ORDER BY id DESC
                """,
                (selected_iso,),
            ).fetchall()

    return [dict(row) for row in rows]


def delete_ticket(ticket_id: int) -> None:
    with get_connection() as conn:
        before = {
            "ticket": _fetch_ticket(conn, ticket_id),
            "comments": _fetch_ticket_comments(conn, ticket_id),
            "daily_updates": _fetch_ticket_updates(conn, ticket_id),
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
    "inbound_calls",
    "outbound_calls",
    "calls_failed",
    "moor_chat",
    "first_call_resolved",
    "emails",
    "tickets_hq_help",
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
                fecha, inbound_calls, outbound_calls, calls_failed, moor_chat,
                first_call_resolved, emails, tickets_hq_help, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fecha) DO UPDATE SET
                inbound_calls = excluded.inbound_calls,
                outbound_calls = excluded.outbound_calls,
                calls_failed = excluded.calls_failed,
                moor_chat = excluded.moor_chat,
                first_call_resolved = excluded.first_call_resolved,
                emails = excluded.emails,
                tickets_hq_help = excluded.tickets_hq_help,
                updated_at = excluded.updated_at
            """,
            (
                report_date.isoformat(),
                values["inbound_calls"],
                values["outbound_calls"],
                values["calls_failed"],
                values["moor_chat"],
                values["first_call_resolved"],
                values["emails"],
                values["tickets_hq_help"],
                now,
            ),
        )


def count_daily_report_tickets(report_date: date) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT tickets.id) AS total
            FROM tickets
            LEFT JOIN ticket_daily_updates
              ON ticket_daily_updates.ticket_id = tickets.id
             AND ticket_daily_updates.fecha = ?
            WHERE tickets.fecha_creacion = ?
               OR ticket_daily_updates.ticket_id IS NOT NULL
            """,
            (report_date.isoformat(), report_date.isoformat()),
        ).fetchone()
    return int(row["total"] or 0)


def build_daily_report_message(report_date: date, data: dict[str, int]) -> str:
    formatted_date = f"{report_date.day} {MONTHS_ES[report_date.month]} {report_date.year}"
    ticket_count = count_daily_report_tickets(report_date)
    values = {field: int(data.get(field, 0)) for field in DAILY_REPORT_FIELDS}
    return "\n".join(
        [
            f"Hi Neil, here is my report of today Report - {formatted_date}",
            "",
            f"Tickets: {ticket_count}",
            "",
            "Jimi:",
            f"-Inbound calls: {values['inbound_calls']}",
            f"-Outbound calls: {values['outbound_calls']}",
            f"-calls Failed to connect: {values['calls_failed']}",
            f"-7 moor platform online chat: {values['moor_chat']}",
            f"-Issues resolved over the first call: {values['first_call_resolved']}",
            f"-Emails: {values['emails']}",
            f"-Tickets needing HQ help or attention: {values['tickets_hq_help']}",
        ]
    )


def update_ticket_estado(ticket_id: int, estado: str, update_date: date | None = None) -> None:
    estado = estado.strip()
    if estado not in DEFAULT_ESTADOS:
        raise ValueError("Estado invalido.")

    with get_connection() as conn:
        before = {"ticket": _fetch_ticket(conn, ticket_id), "daily_update": None, "update_date": None}
        if before["ticket"] is None:
            return
        if update_date:
            before["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
            before["update_date"] = update_date.isoformat()
        conn.execute("UPDATE tickets SET estado = ? WHERE id = ?", (estado, ticket_id))
        if update_date:
            _mark_ticket_updated_with_conn(conn, ticket_id, update_date)
        after = {"ticket": _fetch_ticket(conn, ticket_id), "daily_update": None, "update_date": before["update_date"]}
        if update_date:
            after["daily_update"] = _fetch_daily_update(conn, ticket_id, update_date)
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

        action = dict(row)
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
        else:
            raise ValueError("No se pudo revertir la ultima accion.")

        conn.execute("UPDATE action_history SET undone = 1 WHERE id = ?", (action["id"],))
        return description


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
