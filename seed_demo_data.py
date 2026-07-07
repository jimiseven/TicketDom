from __future__ import annotations

from datetime import date, datetime, timedelta

from database import initialize_database, get_connection
import services


DEMO_PREFIX = "DEMO-"


def seed_demo_data() -> None:
    initialize_database()
    today = date.today()

    for country in ("United States", "Canada", "Mexico", "Dominican Republic"):
        services.add_option("pais", country)

    for estado_actual in (
        "Awaiting hq team response",
        "Awaiting customer response",
        "Monitoring fix",
        "Pending engineering review",
    ):
        services.add_option("estado_actual", estado_actual)

    with get_connection() as conn:
        conn.execute("DELETE FROM tickets WHERE numero_ticket LIKE ?", (f"{DEMO_PREFIX}%",))

    tickets = [
        {
            "days_ago": 6,
            "numero_ticket": "DEMO-1001",
            "pais": "United States",
            "mail": "alice@example.com",
            "phone": "+1 555 0101",
            "estado": "pendiente",
            "problem_name": "Payment gateway timeout",
            "description": "Customer reports intermittent timeout when paying with card.",
            "estado_actual": "Pending engineering review",
            "comments": ["Initial review completed.", "Escalated to engineering team."],
        },
        {
            "days_ago": 5,
            "numero_ticket": "DEMO-1002",
            "pais": "Canada",
            "mail": "support.ca@example.com",
            "phone": "+1 555 0102",
            "estado": "respondido",
            "problem_name": "Unable to reset password",
            "description": "User is waiting for confirmation after password reset troubleshooting.",
            "estado_actual": "Awaiting customer response",
            "comments": ["Sent reset steps to customer."],
        },
        {
            "days_ago": 4,
            "numero_ticket": "DEMO-1003",
            "pais": "Mexico",
            "mail": "ops.mx@example.com",
            "phone": "+52 55 0103",
            "estado": "cerrado",
            "problem_name": "Duplicate invoice generated",
            "description": "Duplicate invoice was voided and customer confirmed resolution.",
            "estado_actual": "Awaiting customer response",
            "comments": ["Invoice voided.", "Customer confirmed closure."],
        },
        {
            "days_ago": 3,
            "numero_ticket": "DEMO-1004",
            "pais": "United States",
            "mail": "network@example.com",
            "phone": "+1 555 0104",
            "estado": "critico",
            "problem_name": "SMS delivery degraded",
            "description": "Critical SMS delivery degradation affecting multiple users.",
            "estado_actual": "Awaiting hq team response",
            "comments": ["Provider status checked.", "HQ team notified."],
        },
        {
            "days_ago": 2,
            "numero_ticket": "DEMO-1005",
            "pais": "Dominican Republic",
            "mail": "",
            "phone": "+1 809 0105",
            "estado": "no tomado",
            "problem_name": "",
            "description": "Ticket created with partial information for edit-flow testing.",
            "estado_actual": "Awaiting customer response",
            "comments": [],
        },
        {
            "days_ago": 1,
            "numero_ticket": "DEMO-1006",
            "pais": "Canada",
            "mail": "qa.ca@example.com",
            "phone": "",
            "estado": "pendiente",
            "problem_name": "Report export missing rows",
            "description": "Exported report has fewer rows than dashboard view.",
            "estado_actual": "Monitoring fix",
            "comments": ["Reproduced issue with demo account."],
        },
        {
            "days_ago": 0,
            "numero_ticket": "DEMO-1007",
            "pais": "United States",
            "mail": "today@example.com",
            "phone": "+1 555 0107",
            "estado": "pendiente",
            "problem_name": "New login alert issue",
            "description": "Customer opened a new same-day ticket.",
            "estado_actual": "Awaiting hq team response",
            "comments": ["Ticket received today."],
        },
        {
            "days_ago": 0,
            "numero_ticket": "DEMO-1008",
            "pais": "Mexico",
            "mail": "closed.today@example.com",
            "phone": "+52 55 0108",
            "estado": "cerrado",
            "problem_name": "Resolved same-day case",
            "description": "Same-day ticket already closed.",
            "estado_actual": "Awaiting customer response",
            "comments": ["Resolved during first contact."],
        },
    ]

    for item in tickets:
        ticket_date = today - timedelta(days=item["days_ago"])
        ticket_id = services.create_ticket(
            {
                "fecha_creacion": ticket_date.isoformat(),
                "pais": item["pais"],
                "numero_ticket": item["numero_ticket"],
                "mail": item["mail"],
                "phone": item["phone"],
                "estado": item["estado"],
                "problem_name": item["problem_name"],
                "description": item["description"],
                "estado_actual": item["estado_actual"],
            }
        )
        for offset, comment in enumerate(item["comments"]):
            comment_time = datetime.combine(ticket_date, datetime.min.time()) + timedelta(hours=9 + offset)
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO comentarios (ticket_id, fecha_hora, comentario) VALUES (?, ?, ?)",
                    (ticket_id, comment_time.strftime("%Y-%m-%d %H:%M:%S"), comment),
                )


if __name__ == "__main__":
    seed_demo_data()
    print("Demo data inserted. Run: python app.py")
