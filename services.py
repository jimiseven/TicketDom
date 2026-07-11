from __future__ import annotations

from datetime import date, datetime
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
        return int(cursor.lastrowid)


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


def update_ticket(ticket_id: int, ticket_data: dict[str, str]) -> None:
    required_fields = ("fecha_creacion", "pais", "estado", "estado_actual")
    missing = [field for field in required_fields if not ticket_data.get(field, "").strip()]
    if missing:
        raise ValueError("Completa los campos obligatorios: " + ", ".join(missing))

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tickets
            SET fecha_creacion = ?, pais = ?, numero_ticket = ?, mail = ?, phone = ?,
                estado = ?, problem_name = ?, description = ?, estado_actual = ?
            WHERE id = ?
            """,
            (
                ticket_data["fecha_creacion"].strip(),
                ticket_data["pais"].strip(),
                ticket_data.get("numero_ticket", "").strip(),
                ticket_data.get("mail", "").strip(),
                ticket_data.get("phone", "").strip(),
                ticket_data["estado"].strip(),
                ticket_data.get("problem_name", "").strip(),
                ticket_data.get("description", "").strip(),
                ticket_data["estado_actual"].strip(),
                ticket_id,
            ),
        )


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
        conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))


def delete_tickets(ticket_ids: list[int]) -> None:
    if not ticket_ids:
        return

    placeholders = ",".join("?" for _ in ticket_ids)
    with get_connection() as conn:
        conn.execute(f"DELETE FROM tickets WHERE id IN ({placeholders})", ticket_ids)


def mark_ticket_updated(ticket_id: int, update_date: date) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ticket_daily_updates (ticket_id, fecha, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(ticket_id, fecha) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (ticket_id, update_date.isoformat(), now),
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


def update_ticket_estado(ticket_id: int, estado: str) -> None:
    estado = estado.strip()
    if estado not in DEFAULT_ESTADOS:
        raise ValueError("Estado invalido.")

    with get_connection() as conn:
        conn.execute("UPDATE tickets SET estado = ? WHERE id = ?", (estado, ticket_id))


def update_ticket_estado_actual(ticket_id: int, estado_actual: str) -> None:
    estado_actual = estado_actual.strip()
    if not estado_actual:
        raise ValueError("Estado actual invalido.")

    with get_connection() as conn:
        conn.execute(
            "UPDATE tickets SET estado_actual = ? WHERE id = ?",
            (estado_actual, ticket_id),
        )


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


def add_comment(ticket_id: int, comentario: str) -> None:
    comentario = comentario.strip()
    if not comentario:
        raise ValueError("El comentario no puede estar vacio.")

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO comentarios (ticket_id, fecha_hora, comentario) VALUES (?, ?, ?)",
            (ticket_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comentario),
        )


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
