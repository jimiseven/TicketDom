from __future__ import annotations

from datetime import date, timedelta
import shutil
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
from tkcalendar import DateEntry

import services
from database import DB_PATH, initialize_database


ADD_NEW_OPTION = "<Añadir Nuevo...>"


def _focus_next(event: tk.Event) -> str:
    event.widget.tk_focusNext().focus_set()
    return "break"


def _focus_previous(event: tk.Event) -> str:
    event.widget.tk_focusPrev().focus_set()
    return "break"


def _bind_textbox_navigation(textbox: ctk.CTkTextbox, submit_command=None) -> None:
    def submit(_event: tk.Event) -> str:
        if submit_command:
            submit_command()
        return "break"

    for widget in (textbox, getattr(textbox, "_textbox", None)):
        if widget is None:
            continue
        widget.bind("<Tab>", _focus_next)
        widget.bind("<Shift-Tab>", _focus_previous)
        widget.bind("<ISO_Left_Tab>", _focus_previous)
        widget.bind("<Control-Return>", submit)
        widget.bind("<Control-KP_Enter>", submit)


def _event_in_textbox(widget: tk.Widget, textboxes: tuple[ctk.CTkTextbox, ...]) -> bool:
    while widget is not None:
        if any(widget == textbox or widget == getattr(textbox, "_textbox", None) for textbox in textboxes):
            return True
        widget = widget.master
    return False


def _bind_modal_shortcuts(
    window: tk.Toplevel,
    submit_command=None,
    close_command=None,
    textboxes: tuple[ctk.CTkTextbox, ...] = (),
) -> None:
    close = close_command or window.destroy

    def close_handler(_event: tk.Event) -> str:
        close()
        return "break"

    def submit_handler(event: tk.Event) -> str | None:
        if _event_in_textbox(event.widget, textboxes):
            return None
        if submit_command:
            submit_command()
            return "break"
        return None

    window.bind("<Escape>", close_handler)
    window.bind("<Return>", submit_handler)
    window.bind("<KP_Enter>", submit_handler)
    for textbox in textboxes:
        _bind_textbox_navigation(textbox, submit_command)


class TicketApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        initialize_database()

        self.title("TicketDom - Gestion Local de Tickets")
        self.geometry("1320x760")
        self.minsize(1120, 680)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.visible_tickets: list[dict[str, object]] = []
        self.pais_values: list[str] = []
        self.estado_actual_values: list[str] = []
        self.selected_ticket_ids: set[int] = set()
        self.updated_ticket_ids: set[int] = set()
        self.table_columns = self._default_table_columns()
        self.header_drag: dict[str, object] | None = None
        self.sort_config: dict[str, str] | None = None
        self.search_var = tk.StringVar()

        self._build_layout()
        self._reload_dynamic_options()
        self.floating_badge = FloatingBadge(self)
        self._load_tickets()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(self, corner_radius=0, fg_color="#18181b")
        top_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        top_bar.grid_columnconfigure(2, weight=1)

        def make_group(row: int, column: int, title: str, weight: int = 0) -> ctk.CTkFrame:
            group = ctk.CTkFrame(top_bar, fg_color="#27272a", corner_radius=12)
            group.grid(row=row, column=column, sticky="nsew", padx=(12 if column == 0 else 4, 4), pady=(10 if row == 0 else 0, 10))
            group.grid_columnconfigure(0, weight=weight)
            ctk.CTkLabel(
                group,
                text=title.upper(),
                text_color="#a1a1aa",
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=0, columnspan=10, sticky="w", padx=10, pady=(7, 1))
            return group

        ops_group = make_group(0, 0, "Operaciones")
        self.date_entry = DateEntry(ops_group, date_pattern="yyyy-mm-dd", width=12)
        self.date_entry.set_date(date.today())
        self.date_entry.grid(row=1, column=0, padx=(10, 2), pady=(2, 10))
        self.date_entry.bind("<<DateEntrySelected>>", lambda _e: self._load_tickets())
        ctk.CTkButton(ops_group, text="<", width=30, command=lambda: self._change_selected_day(-1)).grid(
            row=1, column=1, padx=1, pady=(2, 10)
        )
        ctk.CTkButton(ops_group, text=">", width=30, command=lambda: self._change_selected_day(1)).grid(
            row=1, column=2, padx=1, pady=(2, 10)
        )
        ctk.CTkButton(ops_group, text="Ir", width=34, command=self._load_tickets).grid(
            row=1, column=3, padx=(1, 6), pady=(2, 10)
        )
        ctk.CTkButton(
            ops_group,
            text="Nuevo",
            command=self._open_create_modal,
            fg_color="#16a34a",
            hover_color="#15803d",
            width=72,
        ).grid(row=1, column=4, padx=2, pady=(2, 10))
        ctk.CTkButton(
            ops_group,
            text="Lista",
            command=self._open_bulk_modal,
            fg_color="#0891b2",
            hover_color="#0e7490",
            width=62,
        ).grid(row=1, column=5, padx=2, pady=(2, 10))
        ctk.CTkButton(
            ops_group,
            text="Refrescar",
            command=self._load_tickets,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            width=78,
        ).grid(row=1, column=6, padx=2, pady=(2, 10))

        search_group = make_group(0, 1, "Busqueda", weight=1)
        search_entry = ctk.CTkEntry(
            search_group,
            textvariable=self.search_var,
            placeholder_text="Buscar ticket, correo o telefono",
        )
        search_entry.grid(row=1, column=0, sticky="ew", padx=(10, 5), pady=(2, 10))
        search_entry.bind("<Return>", lambda _e: self._load_tickets())
        ctk.CTkButton(search_group, text="Buscar", command=self._load_tickets, width=72).grid(
            row=1, column=1, padx=4, pady=(2, 10)
        )
        ctk.CTkButton(
            search_group,
            text="X",
            command=self._clear_search,
            width=34,
            fg_color="#52525b",
            hover_color="#3f3f46",
        ).grid(row=1, column=2, padx=(4, 10), pady=(2, 10))

        report_group = make_group(0, 2, "Reportes")
        ctk.CTkButton(
            report_group,
            text="SMS",
            command=self._copy_sms_report,
            fg_color="#d97706",
            hover_color="#b45309",
            width=66,
        ).grid(row=1, column=0, padx=(10, 4), pady=(2, 10))
        ctk.CTkButton(
            report_group,
            text="Diario",
            command=self._open_daily_report_modal,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            width=72,
        ).grid(row=1, column=1, padx=(4, 10), pady=(2, 10))

        admin_group = make_group(1, 0, "Admin", weight=1)
        ctk.CTkButton(admin_group, text="Exportar", command=self._export_database, width=82).grid(
            row=1, column=0, padx=(10, 4), pady=(2, 10)
        )
        ctk.CTkButton(admin_group, text="Importar", command=self._import_database, width=82).grid(
            row=1, column=1, padx=4, pady=(2, 10)
        )
        ctk.CTkButton(
            admin_group,
            text="Revertir",
            command=self._revert_last_action,
            fg_color="#9333ea",
            hover_color="#7e22ce",
            width=78,
        ).grid(row=1, column=2, padx=4, pady=(2, 10))
        ctk.CTkButton(
            admin_group,
            text="Historial",
            command=self._open_history_modal,
            fg_color="#475569",
            hover_color="#334155",
            width=78,
        ).grid(row=1, column=3, padx=4, pady=(2, 10))
        ctk.CTkButton(
            admin_group,
            text="Eliminar",
            command=self._delete_selected_tickets,
            fg_color="#dc2626",
            hover_color="#991b1b",
            width=78,
        ).grid(row=1, column=4, padx=4, pady=(2, 10))
        ctk.CTkButton(
            admin_group,
            text="Defecto",
            command=self._reset_table_columns,
            fg_color="#52525b",
            hover_color="#3f3f46",
            width=74,
        ).grid(row=1, column=5, padx=(4, 10), pady=(2, 10))


        self.table_container = ctk.CTkFrame(self)
        self.table_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        self.table_container.grid_columnconfigure(0, weight=1)
        self.table_container.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.table_container,
            text="Tickets visibles",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        # Treeview
        self.tree_frame = ctk.CTkFrame(self.table_container, fg_color="#18181b")
        self.tree_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=(0, 8))
        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
            background="#202024", foreground="#f4f4f5",
            fieldbackground="#202024", rowheight=28,
            font=("Segoe UI", 10), borderwidth=0,
        )
        style.configure("Treeview.Heading",
            background="#3f3f46", foreground="#f4f4f5",
            font=("Segoe UI", 10, "bold"), borderwidth=0,
            relief="flat",
        )
        style.map("Treeview",
            background=[("selected", "#1a2a3f")],
            foreground=[("selected", "#f4f4f5")],
        )
        style.map("Treeview.Heading",
            background=[("active", "#52525b")],
        )

        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=self._tree_columns(),
            show="headings",
            selectmode="none",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        tree_vscroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        tree_vscroll.grid(row=0, column=1, sticky="ns")
        tree_hscroll = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        tree_hscroll.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=tree_vscroll.set, xscrollcommand=tree_hscroll.set)

        self.tree.tag_configure("even", background="#18181b")
        self.tree.tag_configure("odd", background="#202024")
        self.tree.tag_configure("selected", background="#1a2a3f")
        self.tree.tag_configure("rollover", foreground="#f97316")
        self.tree.tag_configure("unupdated", foreground="#f87171")
        self.tree.tag_configure("updated", foreground="#4ade80")
        self.tree.tag_configure("estado_critico", foreground="#fecaca", background="#2d0a0a")
        self.tree.tag_configure("estado_pendiente", foreground="#fef3c7", background="#2d1b04")
        self.tree.tag_configure("estado_cerrado", foreground="#71717a")
        self.tree.tag_configure("estado_no tomado", foreground="#71717a")
        self.tree.tag_configure("estado_respondido", foreground="#dcfce7", background="#052e16")

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double)
        self.tree.bind("<Button-3>", self._on_tree_right)

    def _tree_columns(self) -> list[str]:
        return ["number", "days", "fecha", "pais", "ticket", "updated",
                "mail", "phone", "estado", "problem", "last_comment", "estado_actual"]

    def _tree_headers(self) -> dict[str, str]:
        return {
            "number": "#", "days": "Dias", "fecha": "Fecha", "pais": "Pais",
            "ticket": "Ticket", "updated": "Actualizado", "mail": "Mail",
            "phone": "Phone", "estado": "Estado", "problem": "Problema",
            "last_comment": "Ultimo Comentario", "estado_actual": "Estado Actual",
        }

    def _default_table_columns(self) -> list[dict[str, object]]:
        return [
            {"key": "select", "title": "Sel", "width": 44},
            {"key": "number", "title": "#", "width": 36},
            {"key": "days", "title": "Dias", "width": 48},
            {"key": "fecha", "title": "Fecha", "width": 90},
            {"key": "pais", "title": "Pais", "width": 80},
            {"key": "ticket", "title": "Ticket", "width": 180},
            {"key": "updated", "title": "Actualizado", "width": 130},
            {"key": "mail", "title": "Mail", "width": 125},
            {"key": "phone", "title": "Phone", "width": 90},
            {"key": "estado", "title": "Estado", "width": 112},
            {"key": "problem", "title": "Problema", "width": 135},
            {"key": "last_comment", "title": "Ultimo Comentario", "width": 190},
            {"key": "estado_actual", "title": "Estado Actual", "width": 145},
            {"key": "actions", "title": "Opciones", "width": 150},
        ]

    def _open_create_modal(self) -> None:
        CreateTicketModal(self)

    def _open_bulk_modal(self) -> None:
        BulkTicketModal(self)

    def _open_daily_report_modal(self) -> None:
        DailyReportModal(self)

    def _open_history_modal(self) -> None:
        ActionHistoryModal(self)

    def _show_toast(self, message: str) -> None:
        toast = ctk.CTkToplevel(self)
        toast.title("")
        toast.geometry("280x60")
        toast.resizable(False, False)
        toast.transient(self)
        toast.attributes("-topmost", True)
        ctk.CTkLabel(
            toast,
            text=message,
            font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=260,
        ).pack(expand=True, fill="both", padx=12, pady=12)
        toast.after(300, toast.destroy)

    def _reset_table_columns(self) -> None:
        self.table_columns = self._default_table_columns()
        self.sort_config = None
        self._tree_cols_set = False
        self._load_tickets()

    def _export_database(self) -> None:
        target_path = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar base de datos",
            defaultextension=".db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
            initialfile="tickets_data_backup.db",
        )
        if not target_path:
            return

        try:
            shutil.copy2(DB_PATH, target_path)
        except OSError as exc:
            messagebox.showerror("Exportar DB", f"No se pudo exportar la base de datos:\n{exc}", parent=self)
            return
        messagebox.showinfo("Exportar DB", "Base de datos exportada correctamente.", parent=self)

    def _import_database(self) -> None:
        source_path = filedialog.askopenfilename(
            parent=self,
            title="Importar base de datos",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if not source_path:
            return

        confirmed = messagebox.askyesno(
            "Importar DB",
            "Esto reemplazara la base de datos actual. Continuar?",
            parent=self,
        )
        if not confirmed:
            return

        try:
            shutil.copy2(source_path, DB_PATH)
            initialize_database()
        except OSError as exc:
            messagebox.showerror("Importar DB", f"No se pudo importar la base de datos:\n{exc}", parent=self)
            return

        self._reload_dynamic_options()
        self._load_tickets()
        messagebox.showinfo("Importar DB", "Base de datos importada correctamente.", parent=self)

    def _build_form(self) -> None:
        self.form_frame.grid_columnconfigure(0, weight=1)
        self.pais_combo = self._combo(row=1, label="Pais")
        self.ticket_entry = self._entry(row=3, label="Numero Ticket")
        self.mail_entry = self._entry(row=5, label="Mail")
        self.phone_entry = self._entry(row=7, label="Phone")

        ctk.CTkLabel(self.form_frame, text="Estado").grid(row=9, column=0, sticky="w", padx=16)
        self.estado_combo = ctk.CTkComboBox(self.form_frame, values=list(services.get_estados()))
        self.estado_combo.grid(row=10, column=0, sticky="ew", padx=16, pady=(4, 10))

        self.problem_entry = self._entry(row=11, label="Problem Name")

        ctk.CTkLabel(self.form_frame, text="Descripcion").grid(row=13, column=0, sticky="w", padx=16)
        self.description_text = ctk.CTkTextbox(self.form_frame, height=80)
        self.description_text.grid(row=14, column=0, sticky="ew", padx=16, pady=(4, 10))

        ctk.CTkLabel(self.form_frame, text="Estado Actual").grid(row=15, column=0, sticky="w", padx=16)
        self.estado_actual_combo = ctk.CTkComboBox(
            self.form_frame,
            values=[],
            command=lambda value: self._handle_dynamic_option("estado_actual", value),
        )
        self.estado_actual_combo.grid(row=16, column=0, sticky="ew", padx=16, pady=(4, 12))

        ctk.CTkButton(self.form_frame, text="Guardar Ticket", command=self._save_ticket).grid(
            row=17, column=0, sticky="ew", padx=16, pady=(8, 8)
        )
        ctk.CTkButton(self.form_frame, text="Limpiar", command=self._clear_form, fg_color="#52525b").grid(
            row=18, column=0, sticky="ew", padx=16, pady=(0, 16)
        )

    def _entry(self, row: int, label: str) -> ctk.CTkEntry:
        ctk.CTkLabel(self.form_frame, text=label).grid(row=row, column=0, sticky="w", padx=16)
        entry = ctk.CTkEntry(self.form_frame)
        entry.grid(row=row + 1, column=0, sticky="ew", padx=16, pady=(4, 10))
        return entry

    def _combo(self, row: int, label: str) -> ctk.CTkComboBox:
        ctk.CTkLabel(self.form_frame, text=label).grid(row=row, column=0, sticky="w", padx=16)
        combo = ctk.CTkComboBox(
            self.form_frame,
            values=[],
            command=lambda value: self._handle_dynamic_option("pais", value),
        )
        combo.grid(row=row + 1, column=0, sticky="ew", padx=16, pady=(4, 10))
        return combo

    def _reload_dynamic_options(self) -> None:
        self.pais_values = services.get_options("pais")
        self.estado_actual_values = services.get_options("estado_actual")
        if hasattr(self, "pais_combo"):
            self.pais_combo.configure(values=self.pais_values + [ADD_NEW_OPTION])
        if hasattr(self, "estado_actual_combo"):
            self.estado_actual_combo.configure(values=self.estado_actual_values + [ADD_NEW_OPTION])

    def _handle_dynamic_option(self, tipo: str, value: str) -> None:
        if value != ADD_NEW_OPTION:
            return

        label = "pais" if tipo == "pais" else "estado actual"
        new_value = simpledialog.askstring("Nueva opcion", f"Ingresa nuevo {label}:", parent=self)
        if not new_value:
            self._set_default_dynamic_values()
            return

        try:
            saved_value = services.add_option(tipo, new_value)
        except ValueError as exc:
            messagebox.showerror("Dato invalido", str(exc), parent=self)
            self._set_default_dynamic_values()
            return

        self._reload_dynamic_options()
        if tipo == "pais":
            self.pais_combo.set(saved_value)
        else:
            self.estado_actual_combo.set(saved_value)

    def _set_default_dynamic_values(self) -> None:
        if self.pais_values and hasattr(self, "pais_combo"):
            self.pais_combo.set(self.pais_values[0])
        if self.estado_actual_values and hasattr(self, "estado_actual_combo"):
            self.estado_actual_combo.set(self.estado_actual_values[0])

    def _selected_date(self) -> date:
        return self.date_entry.get_date()

    def _change_selected_day(self, days: int) -> None:
        self.date_entry.set_date(self._selected_date() + timedelta(days=days))
        self._load_tickets()

    def _clear_search(self) -> None:
        self.search_var.set("")
        self._load_tickets()

    def _save_ticket(self) -> None:
        data = {
            "fecha_creacion": self._selected_date().isoformat(),
            "pais": self.pais_combo.get(),
            "numero_ticket": self.ticket_entry.get(),
            "mail": self.mail_entry.get(),
            "phone": self.phone_entry.get(),
            "estado": self.estado_combo.get(),
            "problem_name": self.problem_entry.get(),
            "description": self.description_text.get("1.0", "end").strip(),
            "estado_actual": self.estado_actual_combo.get(),
        }

        try:
            services.create_ticket(data)
        except ValueError as exc:
            messagebox.showerror("Campos incompletos", str(exc), parent=self)
            return

        self._clear_form()
        self._load_tickets()
        messagebox.showinfo("Ticket guardado", "El ticket fue guardado correctamente.", parent=self)

    def _clear_form(self) -> None:
        for entry in (
            getattr(self, "ticket_entry", None),
            getattr(self, "mail_entry", None),
            getattr(self, "phone_entry", None),
            getattr(self, "problem_entry", None),
        ):
            if entry:
                entry.delete(0, "end")
        if hasattr(self, "description_text"):
            self.description_text.delete("1.0", "end")
        if hasattr(self, "estado_combo"):
            self.estado_combo.set("pendiente")
        self._set_default_dynamic_values()

    def _load_tickets(self) -> None:
        self.visible_tickets = services.get_visible_tickets(self._selected_date())
        self._apply_search_filter()
        visible_ids = {int(ticket["id"]) for ticket in self.visible_tickets}
        self.selected_ticket_ids.intersection_update(visible_ids)
        self.updated_ticket_ids = services.get_updated_ticket_ids(sorted(visible_ids), self._selected_date())
        self._apply_sort()
        self._render_ticket_grid()
        self._update_floating_badge()

    def _update_floating_badge(self) -> None:
        open_count = sum(
            1 for t in self.visible_tickets
            if str(t["estado"]).lower() not in {"cerrado", "no tomado"}
        )
        unupdated = sum(
            1 for t in self.visible_tickets
            if str(t["estado"]).lower() in {"respondido", "pendiente", "critico"}
            and int(t["id"]) not in self.updated_ticket_ids
        )
        self.floating_badge.update_count(open_count, unupdated)

    def _apply_search_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        if not query:
            return

        self.visible_tickets = [
            ticket
            for ticket in self.visible_tickets
            if query in str(ticket.get("numero_ticket") or "").lower()
            or query in str(ticket.get("mail") or "").lower()
            or query in str(ticket.get("phone") or "").lower()
        ]

    def _render_ticket_grid(self) -> None:
        tree = self.tree
        for item in tree.get_children():
            tree.delete(item)

        cols = self._tree_columns()
        headers = self._tree_headers()
        widths = {"number": 30, "days": 36, "fecha": 85, "pais": 76, "ticket": 170,
                  "updated": 80, "mail": 120, "phone": 85, "estado": 95,
                  "problem": 130, "last_comment": 170, "estado_actual": 135}
        stretch_cols = {"ticket", "problem", "last_comment", "estado_actual", "mail"}

        for col in cols:
            tree.heading(col, text=headers[col], anchor="w",
                         command=lambda c=col: self._toggle_sort(c))

        # Only set column widths on first render (preserve user resize)
        if not getattr(self, "_tree_cols_set", False):
            for col in cols:
                tree.column(col, width=widths.get(col, 100), anchor="w", minwidth=30,
                            stretch=col in stretch_cols)
            self._tree_cols_set = True

        if not self.visible_tickets:
            return

        for row_index, ticket in enumerate(self.visible_tickets, start=1):
            ticket_id = int(ticket["id"])
            estado = str(ticket["estado"]).lower()
            days_open = self._days_open(str(ticket["fecha_creacion"]))
            updated_st = self._ticket_update_status(ticket)
            comment_count = int(ticket.get("comment_count") or 0)
            ticket_text = str(ticket["numero_ticket"] or "")
            if comment_count:
                ticket_text += f" (C{comment_count})"

            values = {
                "number": str(row_index),
                "days": str(days_open),
                "fecha": ticket["fecha_creacion"],
                "pais": ticket["pais"],
                "ticket": ticket_text,
                "updated": updated_st,
                "mail": ticket.get("mail") or "-",
                "phone": ticket.get("phone") or "-",
                "estado": estado.capitalize(),
                "problem": ticket.get("problem_name") or "-",
                "last_comment": ticket.get("last_comment") or "-",
                "estado_actual": ticket.get("estado_actual") or "-",
            }
            row_vals = [values[c] for c in cols]

            tags = ["even" if row_index % 2 == 0 else "odd"]
            if ticket_id in self.selected_ticket_ids:
                tags.append("selected")
            if ticket.get("is_rollover"):
                tags.append("rollover")
            if updated_st == "No":
                tags.append("unupdated")
            if updated_st == "Si":
                tags.append("updated")
            estado_tag = f"estado_{estado}"
            if estado_tag in ("estado_cerrado", "estado_no tomado", "estado_critico",
                              "estado_pendiente", "estado_respondido"):
                tags.append(estado_tag)

            tree.insert("", "end", iid=str(ticket_id), values=row_vals, tags=tags)

    def _on_tree_click(self, event: tk.Event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        ticket_id = int(item)
        col = self.tree.identify_column(event.x)
        col_idx = int(col.replace("#", "")) - 1
        col_key = self._tree_columns()[col_idx] if 0 <= col_idx < len(self._tree_columns()) else ""

        if col_key == "ticket":
            tree_vals = self.tree.item(item, "values")
            if tree_vals:
                idx = self._tree_columns().index("ticket")
                ticket_val = str(tree_vals[idx]).split(" ")[0]
                if ticket_val:
                    self.clipboard_clear()
                    self.clipboard_append(ticket_val)
                    self._show_toast("Ticket copiado: " + ticket_val)
            return

        if col_key == "updated":
            current = "Si" if ticket_id in self.updated_ticket_ids else "No"
            self._toggle_ticket_updated(ticket_id, current)
            return

        if col_key == "estado":
            menu = tk.Menu(self, tearoff=0, bg="#27272a", fg="#f4f4f5",
                           activebackground="#3f3f46", activeforeground="#f4f4f5")
            for est in services.get_estados():
                menu.add_command(
                    label=est.capitalize(),
                    command=lambda e=est: self._update_ticket_estado(ticket_id, e),
                )
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return

        if col_key == "estado_actual":
            if not self.estado_actual_values:
                return
            menu = tk.Menu(self, tearoff=0, bg="#27272a", fg="#f4f4f5",
                           activebackground="#3f3f46", activeforeground="#f4f4f5")
            for val in self.estado_actual_values:
                menu.add_command(
                    label=val,
                    command=lambda v=val: self._update_ticket_estado_actual(ticket_id, v),
                )
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return

        if col_key == "last_comment":
            self._open_comments_modal(ticket_id)
            return

        # Toggle selection
        if ticket_id in self.selected_ticket_ids:
            self.selected_ticket_ids.discard(ticket_id)
        else:
            self.selected_ticket_ids.add(ticket_id)
        self._render_ticket_grid()

    def _on_tree_double(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self._open_comments_modal(int(item))

    def _on_tree_right(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        ticket_id = int(item)
        menu = tk.Menu(self, tearoff=0, bg="#27272a", fg="#f4f4f5",
                       activebackground="#3f3f46", activeforeground="#f4f4f5")
        menu.add_command(label="Editar ticket", command=lambda: self._open_edit_modal(ticket_id))
        menu.add_command(label="Copiar ticket", command=lambda: self._copy_ticket_from_tree(ticket_id))
        menu.add_command(label="Ver comentarios", command=lambda: self._open_comments_modal(ticket_id))
        menu.add_separator()
        menu.add_command(label="Marcar actualizado", command=lambda: self._mark_item_updated(ticket_id))
        menu.add_command(label="Cambiar estado...",
                         command=lambda: self._cycle_tree_estado(ticket_id))
        menu.add_separator()
        menu.add_command(label="Eliminar ticket",
                         command=lambda: self._delete_ticket(ticket_id),
                         foreground="#f87171")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _mark_item_updated(self, ticket_id: int) -> None:
        services.mark_ticket_updated(ticket_id, self._selected_date())
        self._load_tickets()
        self._show_toast("Ticket marcado como actualizado.")

    def _copy_ticket_from_tree(self, ticket_id: int) -> None:
        ticket = services.get_ticket(ticket_id)
        if ticket and ticket.get("numero_ticket"):
            self.clipboard_clear()
            self.clipboard_append(str(ticket["numero_ticket"]))
            self._show_toast("Ticket copiado: " + str(ticket["numero_ticket"]))

    def _cycle_tree_estado(self, ticket_id: int) -> None:
        estados = list(services.get_estados())
        ticket = services.get_ticket(ticket_id)
        if not ticket:
            return
        current = str(ticket["estado"]).lower()
        try:
            idx = (estados.index(current) + 1) % len(estados)
        except ValueError:
            idx = 0
        new_estado = estados[idx]
        try:
            services.update_ticket_estado(ticket_id, new_estado, status_change_date=self._selected_date())
        except ValueError:
            pass
        self._load_tickets()

    def _ticket_update_status(self, ticket: dict[str, object]) -> str:
        estado = str(ticket["estado"]).lower()
        if estado not in {"respondido", "pendiente", "critico"}:
            return "-"
        ticket_id = int(ticket["id"])
        if ticket_id in self.updated_ticket_ids:
            return "Si"
        return "No"

    def _toggle_ticket_updated(self, ticket_id: int, current_status: str) -> None:
        if current_status == "Si":
            services.unmark_ticket_updated(ticket_id, self._selected_date())
            message = "Ticket marcado como no actualizado."
        else:
            services.mark_ticket_updated(ticket_id, self._selected_date())
            message = "Ticket marcado como actualizado."
        self._load_tickets()
        self._show_toast(message)

    def _toggle_sort(self, key: str) -> None:
        if self.sort_config and self.sort_config["key"] == key:
            direction = "desc" if self.sort_config["direction"] == "asc" else "asc"
        else:
            direction = "asc"
        self.sort_config = {"key": key, "direction": direction}
        self._apply_sort()
        self._render_ticket_grid()

    def _apply_sort(self) -> None:
        if not self.sort_config:
            return
        key = self.sort_config["key"]
        reverse = self.sort_config["direction"] == "desc"
        if key == "fecha":
            self.visible_tickets.sort(key=lambda ticket: (str(ticket["fecha_creacion"]), int(ticket["id"])), reverse=reverse)
        elif key == "updated":
            status_order = {"No": 0, "Si": 1, "-": 2}
            self.visible_tickets.sort(
                key=lambda ticket: (status_order[self._ticket_update_status(ticket)], str(ticket["fecha_creacion"])),
                reverse=reverse,
            )

    def _toggle_ticket_selection(self, ticket_id: int, selected: bool) -> None:
        if selected:
            self.selected_ticket_ids.add(ticket_id)
        else:
            self.selected_ticket_ids.discard(ticket_id)

    def _days_open(self, created_at: str) -> int:
        try:
            created_date = date.fromisoformat(created_at)
        except ValueError:
            return 0
        reference_date = self._selected_date()
        if reference_date == date.today() and created_date < reference_date:
            return (date.today() - created_date).days + 1
        return max(1, (reference_date - created_date).days + 1)

    def _short_text(self, value: str, width: int) -> str:
        max_chars = max(6, width // 8)
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 3] + "..."

    def _delete_ticket(self, ticket_id: int) -> None:
        confirmed = messagebox.askyesno(
            "Eliminar ticket",
            "Esta accion eliminara permanentemente el ticket y sus comentarios. Continuar?",
            parent=self,
        )
        if not confirmed:
            return
        services.delete_ticket(ticket_id)
        self.selected_ticket_ids.discard(ticket_id)
        self._load_tickets()

    def _delete_selected_tickets(self) -> None:
        if not self.selected_ticket_ids:
            messagebox.showinfo("Eliminar marcados", "No hay tickets marcados para eliminar.", parent=self)
            return

        count = len(self.selected_ticket_ids)
        confirmed = messagebox.askyesno(
            "Eliminar marcados",
            f"Esta accion eliminara permanentemente {count} ticket(s) y sus comentarios. Continuar?",
            parent=self,
        )
        if not confirmed:
            return

        services.delete_tickets(sorted(self.selected_ticket_ids))
        self.selected_ticket_ids.clear()
        self._load_tickets()
        messagebox.showinfo("Eliminar marcados", f"Se eliminaron {count} ticket(s).", parent=self)

    def _revert_last_action(self) -> None:
        confirmed = messagebox.askyesno(
            "Revertir ultima accion",
            "Se revertira la ultima accion registrada. Continuar?",
            parent=self,
        )
        if not confirmed:
            return

        try:
            message = services.revert_last_action()
        except ValueError as exc:
            messagebox.showerror("Revertir ultima accion", str(exc), parent=self)
            return

        if not message:
            messagebox.showinfo("Revertir ultima accion", "No hay acciones para revertir.", parent=self)
            return

        self.selected_ticket_ids.clear()
        self._load_tickets()
        self._show_toast(message)

    def _update_ticket_estado(self, ticket_id: int, estado: str) -> None:
        try:
            services.update_ticket_estado(ticket_id, estado, status_change_date=self._selected_date())
        except ValueError as exc:
            messagebox.showerror("Estado invalido", str(exc), parent=self)
            self._load_tickets()
            return
        self._load_tickets()

    def _update_ticket_estado_actual(self, ticket_id: int, estado_actual: str) -> None:
        try:
            services.update_ticket_estado_actual(ticket_id, estado_actual)
        except ValueError as exc:
            messagebox.showerror("Estado actual invalido", str(exc), parent=self)
            self._load_tickets()
            return
        self._load_tickets()

    def _open_comments_modal(self, ticket_id: int) -> None:
        CommentsModal(self, ticket_id)

    def _open_edit_modal(self, ticket_id: int) -> None:
        EditTicketModal(self, ticket_id)

    def _copy_sms_report(self) -> None:
        selected_date = self._selected_date()
        if selected_date != date.today():
            messagebox.showwarning(
                "Reporte SMS",
                "El reporte SMS solo se genera para la fecha actual.",
                parent=self,
            )
            return

        report = services.build_sms_report(self.visible_tickets, selected_date)
        if not report:
            messagebox.showinfo("Reporte SMS", "No hay tickets abiertos para reportar.", parent=self)
            return

        self.clipboard_clear()
        self.clipboard_append(report)
        self.update()
        messagebox.showinfo("Reporte SMS", "Reporte copiado al portapapeles.", parent=self)


class ActionHistoryModal(ctk.CTkToplevel):
    def __init__(self, parent: TicketApp) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Historial de Acciones")
        self.geometry("780x520")
        self.minsize(680, 420)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Historial de acciones recientes",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)
        ctk.CTkLabel(header, text="Ultimas 80 acciones registradas", text_color="#a1a1aa").grid(
            row=1, column=0, sticky="w", padx=12, pady=(0, 10)
        )

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(buttons, text="Cerrar", command=self.destroy).grid(row=0, column=0, sticky="e")

        _bind_modal_shortcuts(self, close_command=self.destroy)
        self._render_history()

    def _render_history(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        history = services.get_action_history()
        headers = ["Fecha/Hora", "Accion", "Ticket", "Estado", ""]
        widths = [155, 220, 190, 90, 90]
        for column, title in enumerate(headers):
            ctk.CTkLabel(
                self.list_frame,
                text=title,
                width=widths[column],
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=column, sticky="w", padx=4, pady=(6, 8))

        if not history:
            ctk.CTkLabel(self.list_frame, text="No hay acciones registradas.").grid(
                row=1, column=0, columnspan=len(headers), sticky="w", padx=8, pady=16
            )
            return

        for r, action in enumerate(history, start=1):
            action_id = int(action["id"])
            is_undone = action["undone"]
            status = "Revertida" if is_undone else "Activa"
            text_color = "#a1a1aa" if is_undone else None
            values = [action["created_at"], action["action"], action["ticket"]]
            for column, value in enumerate(values):
                ctk.CTkLabel(
                    self.list_frame,
                    text=self.parent._short_text(str(value), widths[column]),
                    width=widths[column],
                    anchor="w",
                    text_color=text_color,
                ).grid(row=r, column=column, sticky="w", padx=4, pady=4)
            ctk.CTkLabel(
                self.list_frame,
                text=status,
                width=widths[3],
                fg_color="#3f3f46" if is_undone else "#166534",
                text_color="#e4e4e7" if is_undone else "#dcfce7",
                corner_radius=8,
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=r, column=3, sticky="w", padx=4, pady=4)
            if not is_undone:
                ctk.CTkButton(
                    self.list_frame,
                    text="Revertir",
                    width=widths[4],
                    height=26,
                    fg_color="#9333ea",
                    hover_color="#7e22ce",
                    command=lambda aid=action_id: self._do_revert(aid),
                ).grid(row=r, column=4, sticky="w", padx=4, pady=2)

    def _do_revert(self, action_id: int) -> None:
        confirmed = messagebox.askyesno(
            "Revertir accion",
            "Se revertira esta accion. Continuar?",
            parent=self,
        )
        if not confirmed:
            return
        try:
            message = services.revert_action(action_id)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        if message:
            self.parent._load_tickets()
            self._render_history()
            self.parent._show_toast(message)


class InboundCallPopup(ctk.CTkToplevel):
    """Popup modal para ingresar phone + seleccionar un ticket existente."""

    def __init__(self, parent: DailyReportModal) -> None:
        super().__init__(parent)
        self.parent = parent
        self.result: dict[str, str] | None = None
        self._tickets: list[dict[str, object]] = services.get_all_tickets_for_inbound(parent.report_date)

        self.title("Inbound Call")
        self.geometry("460x220")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Seleccionar ticket:", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(16, 4)
        )

        ticket_display = [
            f"{t['numero_ticket']} - {t['problem_name'][:40]}"
            for t in self._tickets
        ] if self._tickets else ["No hay tickets disponibles"]

        self.ticket_combo = ctk.CTkComboBox(
            self,
            values=ticket_display,
            command=self._on_ticket_selected,
            state="readonly" if self._tickets else "disabled",
        )
        self.ticket_combo.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        if self._tickets:
            self.ticket_combo.set(ticket_display[0])

        ctk.CTkLabel(self, text="Numero de telefono (auto-completado):", anchor="w").grid(
            row=2, column=0, sticky="ew", padx=16, pady=(0, 4)
        )
        self.phone_entry = ctk.CTkEntry(self)
        self.phone_entry.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 10))

        # Auto-fill phone from first ticket
        if self._tickets:
            self._on_ticket_selected(ticket_display[0])

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=4, column=0, sticky="ew", padx=16, pady=(8, 16))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(buttons, text="Agregar", command=self._confirm).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(buttons, text="Cancelar", command=self.destroy, fg_color="#52525b").grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        self.bind("<Return>", lambda _e: self._confirm())
        self.bind("<KP_Enter>", lambda _e: self._confirm())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(100, self.phone_entry.focus_set)

    def _on_ticket_selected(self, selected: str) -> None:
        """Auto-fill phone when a ticket is selected."""
        ticket_num = selected.split(" - ")[0].strip()
        for t in self._tickets:
            if str(t["numero_ticket"]) == ticket_num:
                phone = str(t.get("phone") or "")
                self.phone_entry.delete(0, "end")
                self.phone_entry.insert(0, phone)
                break

    def _confirm(self) -> None:
        phone = self.phone_entry.get().strip()
        if not phone:
            messagebox.showerror("Campo incompleto", "Ingresa el numero de telefono.", parent=self)
            return
        if not self._tickets:
            messagebox.showerror("Sin tickets", "No hay tickets disponibles para seleccionar.", parent=self)
            return

        selected = self.ticket_combo.get()
        # Extract the ticket number from "TKT-001 - problem name" format
        ticket_number = selected.split(" - ")[0].strip()
        self.result = {"phone": phone, "ticket": ticket_number}
        self.destroy()


class InboundDetailsModal(ctk.CTkToplevel):
    """Modal que muestra los detalles de inbound calls registrados."""

    def __init__(self, parent: DailyReportModal, report_date: date) -> None:
        super().__init__(parent)
        self.parent = parent
        self.report_date = report_date

        self.title("Inbound Call Details")
        self.geometry("520x440")
        self.minsize(460, 360)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Registros de llamadas entrantes",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 8))

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(buttons, text="Cerrar", command=self.destroy).grid(
            row=0, column=0, sticky="e"
        )

        _bind_modal_shortcuts(self, close_command=self.destroy)
        self._render_list()

    def _render_list(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        details = services.get_inbound_call_details(self.report_date)
        headers = ["#", "Telefono", "Ticket", ""]
        widths = [36, 170, 170, 80]
        for column, title in enumerate(headers):
            ctk.CTkLabel(
                self.list_frame,
                text=title,
                width=widths[column],
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=column, sticky="w", padx=4, pady=(4, 8))

        if not details:
            ctk.CTkLabel(self.list_frame, text="No hay registros.").grid(
                row=1, column=0, columnspan=4, sticky="w", padx=8, pady=16
            )
            return

        for row_index, call in enumerate(details, start=1):
            call_id = int(call["id"])
            ctk.CTkLabel(
                self.list_frame,
                text=str(row_index),
                width=widths[0],
                anchor="w",
            ).grid(row=row_index, column=0, sticky="w", padx=4, pady=4)
            ctk.CTkLabel(
                self.list_frame,
                text=str(call["phone"]),
                width=widths[1],
                anchor="w",
            ).grid(row=row_index, column=1, sticky="w", padx=4, pady=4)
            ctk.CTkLabel(
                self.list_frame,
                text=str(call["numero_ticket"]),
                width=widths[2],
                anchor="w",
            ).grid(row=row_index, column=2, sticky="w", padx=4, pady=4)
            ctk.CTkButton(
                self.list_frame,
                text="Eliminar",
                width=widths[3],
                height=26,
                fg_color="#dc2626",
                hover_color="#991b1b",
                command=lambda cid=call_id: self._remove_call(cid),
            ).grid(row=row_index, column=3, sticky="w", padx=4, pady=2)

    def _remove_call(self, call_id: int) -> None:
        confirmed = messagebox.askyesno(
            "Eliminar", "Eliminar este registro de llamada?", parent=self
        )
        if not confirmed:
            return
        services.remove_inbound_call(call_id)
        self.parent._refresh_inbound_count()
        self._render_list()


class HQTicketSelectionModal(ctk.CTkToplevel):
    """Modal para seleccionar tickets que necesitan ayuda de HQ."""

    def __init__(self, parent: DailyReportModal, report_date: date) -> None:
        super().__init__(parent)
        self.parent = parent
        self.report_date = report_date

        self.title("Tickets que necesitan ayuda de HQ")
        self.geometry("900x560")
        self.minsize(700, 480)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        formatted_date = f"{report_date.day} {services.MONTHS_ES[report_date.month]} {report_date.year}"
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=f"Seleccion de tickets para ayuda de HQ - {formatted_date}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 8))

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(buttons, text="Cerrar", command=self.destroy).grid(
            row=0, column=0, sticky="e"
        )

        _bind_modal_shortcuts(self, close_command=self.destroy)
        self._render_list()

    def _render_list(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        # Get all tickets (created on or before report date, not cerrado/no tomado)
        open_tickets = services.auto_calc_open_tickets(self.report_date)
        selected_ids = services.get_hq_ticket_ids(self.report_date)

        headers = ["Seleccionar", "Ticket", "Problema"]
        widths = [110, 190, 400]
        for column, title in enumerate(headers):
            ctk.CTkLabel(
                self.list_frame,
                text=title,
                width=widths[column],
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=column, sticky="w", padx=4, pady=(4, 8))

        if not open_tickets:
            ctk.CTkLabel(
                self.list_frame, text="No hay tickets abiertos disponibles."
            ).grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=16)
            return

        for row_index, ticket in enumerate(open_tickets, start=1):
            ticket_id = int(ticket["id"])
            is_selected = ticket_id in selected_ids
            var = tk.BooleanVar(value=is_selected)
            ctk.CTkCheckBox(
                self.list_frame,
                text="",
                width=widths[0],
                variable=var,
                command=lambda tid=ticket_id, v=var: self._toggle(tid, v.get()),
            ).grid(row=row_index, column=0, sticky="w", padx=8, pady=4)
            ctk.CTkLabel(
                self.list_frame,
                text=str(ticket.get("numero_ticket") or "-"),
                width=widths[1],
                anchor="w",
            ).grid(row=row_index, column=1, sticky="w", padx=4, pady=4)
            ctk.CTkLabel(
                self.list_frame,
                text=str(ticket.get("problem_name") or "-"),
                width=widths[2],
                anchor="w",
            ).grid(row=row_index, column=2, sticky="w", padx=4, pady=4)

    def _toggle(self, ticket_id: int, selected: bool) -> None:
        services.set_hq_ticket(self.report_date, ticket_id, selected)
        self.parent._refresh_hq_count()


class DailyReportModal(ctk.CTkToplevel):
    FIELDS = [
        ("outbound_calls", "Outbound calls"),
        ("missed_calls", "Missed calls"),
        ("moor_chat", "7 moor platform online chats"),
        ("goto_chat", "GoTo platform online chats"),
        ("emails", "Emails"),
    ]

    def __init__(self, parent: TicketApp) -> None:
        super().__init__(parent)
        self.parent = parent
        self.report_date = parent._selected_date()
        self.values: dict[str, int] = {}
        self.value_labels: dict[str, ctk.CTkLabel] = {}
        self.inbound_label: ctk.CTkLabel | None = None
        self.hq_label: ctk.CTkLabel | None = None

        self.title("Reporte Diario")
        self.geometry("640x640")
        self.minsize(560, 560)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)

        data = services.get_daily_report(self.report_date)
        formatted_date = (
            f"{self.report_date.day} {services.MONTHS_ES[self.report_date.month]} "
            f"{self.report_date.year}"
        )

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=f"Reporte Diario - {formatted_date}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        body = ctk.CTkScrollableFrame(self, fg_color="#202024")
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)
        body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Helper to add a counter row
        row_counter = [0]

        def _counter_row(field: str, label: str, initial: int = 0) -> None:
            row = row_counter[0]
            self.values[field] = initial
            ctk.CTkLabel(body, text=label).grid(
                row=row, column=0, sticky="w", padx=12, pady=6
            )
            ctk.CTkButton(
                body,
                text="-",
                width=44,
                fg_color="#52525b",
                command=lambda f=field: self._change_counter(f, -1),
            ).grid(row=row, column=1, sticky="e", padx=(6, 4), pady=5)
            value_label = ctk.CTkLabel(
                body,
                text=str(self.values[field]),
                width=64,
                fg_color="#27272a",
                corner_radius=8,
                font=ctk.CTkFont(size=16, weight="bold"),
            )
            value_label.grid(row=row, column=2, padx=4, pady=5)
            self.value_labels[field] = value_label
            ctk.CTkButton(
                body,
                text="+1",
                width=58,
                command=lambda f=field: self._change_counter(f, 1),
            ).grid(row=row, column=3, sticky="w", padx=(4, 12), pady=5)
            row_counter[0] = row + 1

        # -- New Tickets (auto-calc with editable counter) --
        new_tickets_initial = int(data.get("new_tickets_count", 0))
        self._new_tickets_list = services.auto_calc_new_tickets(self.report_date)
        if new_tickets_initial == 0:
            new_tickets_initial = len(self._new_tickets_list)

        row = row_counter[0]
        self.values["new_tickets_count"] = new_tickets_initial
        ctk.CTkLabel(
            body, text="New Tickets", font=ctk.CTkFont(weight="bold", size=14)
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkButton(
            body,
            text="-",
            width=44,
            fg_color="#52525b",
            command=lambda: self._change_counter("new_tickets_count", -1),
        ).grid(row=row, column=1, sticky="e", padx=(6, 4), pady=5)
        self.new_tickets_label = ctk.CTkLabel(
            body,
            text=str(self.values["new_tickets_count"]),
            width=64,
            fg_color="#1e3a8a",
            corner_radius=8,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.new_tickets_label.grid(row=row, column=2, padx=4, pady=5)
        self.value_labels["new_tickets_count"] = self.new_tickets_label
        ctk.CTkButton(
            body,
            text="+1",
            width=58,
            command=lambda: self._change_counter("new_tickets_count", 1),
        ).grid(row=row, column=3, sticky="w", padx=(4, 12), pady=5)
        ctk.CTkButton(
            body,
            text="Auto",
            width=48,
            height=26,
            fg_color="#2563eb",
            command=self._auto_calc_new_tickets,
        ).grid(row=row, column=4, padx=(2, 12), pady=5)
        row_counter[0] = row + 1

        # -- Inbound calls (counter + popup on +1) --
        row = row_counter[0]
        ctk.CTkLabel(
            body, text="Inbound calls", font=ctk.CTkFont(weight="bold", size=14)
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        # Count from the details table
        inbound_details = services.get_inbound_call_details(self.report_date)
        inbound_count = len(inbound_details)
        self.values["inbound_calls"] = inbound_count

        self.inbound_label = ctk.CTkLabel(
            body,
            text=str(inbound_count),
            width=64,
            fg_color="#27272a",
            corner_radius=8,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.inbound_label.grid(row=row, column=2, padx=4, pady=5)
        # +1 opens popup
        ctk.CTkButton(
            body,
            text="+1",
            width=58,
            command=self._add_inbound_call,
        ).grid(row=row, column=3, sticky="w", padx=(4, 12), pady=5)
        # View details button
        ctk.CTkButton(
            body,
            text="Ver",
            width=48,
            height=26,
            fg_color="#0891b2",
            command=self._view_inbound_details,
        ).grid(row=row, column=4, padx=(2, 12), pady=5)
        row_counter[0] = row + 1

        # -- Simple counter fields --
        for field, label in self.FIELDS:
            _counter_row(field, label, int(data.get(field, 0)))

        # -- Tickets needing HQ help --
        row = row_counter[0]
        ctk.CTkLabel(
            body, text="Tickets needing HQ help or attention",
            font=ctk.CTkFont(weight="bold", size=14),
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.hq_label = ctk.CTkLabel(
            body,
            text=str(len(self._get_hq_ticket_ids())),
            width=64,
            fg_color="#27272a",
            corner_radius=8,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.hq_label.grid(row=row, column=2, padx=4, pady=5)
        ctk.CTkButton(
            body,
            text="Seleccionar",
            width=86,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=self._open_hq_selection,
        ).grid(row=row, column=3, sticky="w", padx=(4, 12), pady=5)
        row_counter[0] = row + 1

        # -- Open Tickets (auto-calc with editable counter) --
        open_tickets_initial = int(data.get("open_tickets_count", 0))
        if open_tickets_initial == 0:
            open_tickets = services.auto_calc_open_tickets(self.report_date)
            open_tickets_initial = len(open_tickets)

        row = row_counter[0]
        self.values["open_tickets_count"] = open_tickets_initial
        ctk.CTkLabel(
            body, text="Open tickets", font=ctk.CTkFont(weight="bold", size=14)
        ).grid(row=row, column=0, sticky="w", padx=12, pady=6)
        ctk.CTkButton(
            body,
            text="-",
            width=44,
            fg_color="#52525b",
            command=lambda: self._change_counter("open_tickets_count", -1),
        ).grid(row=row, column=1, sticky="e", padx=(6, 4), pady=5)
        self.open_tickets_label = ctk.CTkLabel(
            body,
            text=str(self.values["open_tickets_count"]),
            width=64,
            fg_color="#1e3a8a",
            corner_radius=8,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.open_tickets_label.grid(row=row, column=2, padx=4, pady=5)
        self.value_labels["open_tickets_count"] = self.open_tickets_label
        ctk.CTkButton(
            body,
            text="+1",
            width=58,
            command=lambda: self._change_counter("open_tickets_count", 1),
        ).grid(row=row, column=3, sticky="w", padx=(4, 12), pady=5)
        ctk.CTkButton(
            body,
            text="Auto",
            width=48,
            height=26,
            fg_color="#2563eb",
            command=self._auto_calc_open_tickets,
        ).grid(row=row, column=4, padx=(2, 12), pady=5)
        row_counter[0] = row + 1

        # -- Buttons at the bottom --
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(buttons, text="Guardar y Copiar Mensaje",
                       command=self._copy_message,
                       fg_color="#7c3aed", hover_color="#6d28d9").grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(buttons, text="Solo Guardar",
                       command=self._save,
                       fg_color="#52525b").grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        _bind_modal_shortcuts(self, close_command=self.destroy)

    # --- Inbound calls ---

    def _add_inbound_call(self) -> None:
        popup = InboundCallPopup(self)
        self.wait_window(popup)
        if popup.result:
            services.add_inbound_call(
                self.report_date, popup.result["phone"], popup.result["ticket"]
            )
            self._refresh_inbound_count()

    def _refresh_inbound_count(self) -> None:
        details = services.get_inbound_call_details(self.report_date)
        count = len(details)
        self.values["inbound_calls"] = count
        if self.inbound_label:
            self.inbound_label.configure(text=str(count))

    def _view_inbound_details(self) -> None:
        InboundDetailsModal(self, self.report_date)

    # --- HQ tickets ---

    def _get_hq_ticket_ids(self) -> set[int]:
        return services.get_hq_ticket_ids(self.report_date)

    def _refresh_hq_count(self) -> None:
        count = len(self._get_hq_ticket_ids())
        if self.hq_label:
            self.hq_label.configure(text=str(count))

    def _open_hq_selection(self) -> None:
        HQTicketSelectionModal(self, self.report_date)

    # --- Auto-calc ---

    def _auto_calc_new_tickets(self) -> None:
        tickets = services.auto_calc_new_tickets(self.report_date)
        self._new_tickets_list = tickets
        count = len(tickets)
        self.values["new_tickets_count"] = count
        if self.new_tickets_label:
            self.new_tickets_label.configure(text=str(count))

    def _auto_calc_open_tickets(self) -> None:
        tickets = services.auto_calc_open_tickets(self.report_date)
        count = len(tickets)
        self.values["open_tickets_count"] = count
        if self.open_tickets_label:
            self.open_tickets_label.configure(text=str(count))

    # --- Counter ---

    def _change_counter(self, field: str, delta: int) -> None:
        self.values[field] = max(0, self.values.get(field, 0) + delta)
        if field in self.value_labels and self.value_labels[field]:
            self.value_labels[field].configure(text=str(self.values[field]))

    # --- Save & Copy ---

    def _save(self) -> bool:
        services.save_daily_report(self.report_date, self.values)
        self.parent._show_toast("Reporte diario guardado.")
        self.destroy()
        return True

    def _copy_message(self) -> None:
        services.save_daily_report(self.report_date, self.values)

        inbound_details = services.get_inbound_call_details(self.report_date)
        hq_ids = self._get_hq_ticket_ids()
        # Get ticket numbers for selected HQ tickets
        hq_ticket_numbers: list[str] = []
        if hq_ids:
            with services.get_connection() as conn:
                placeholders = ",".join("?" for _ in hq_ids)
                rows = conn.execute(
                    f"SELECT numero_ticket FROM tickets WHERE id IN ({placeholders})",
                    list(hq_ids),
                ).fetchall()
                hq_ticket_numbers = [str(row["numero_ticket"]) for row in rows if row["numero_ticket"]]

        new_tickets = getattr(self, '_new_tickets_list', services.auto_calc_new_tickets(self.report_date))
        open_tickets = services.auto_calc_open_tickets(self.report_date)

        message = services.build_daily_report_message(
            self.report_date,
            self.values,
            inbound_details=inbound_details,
            hq_ticket_numbers=hq_ticket_numbers,
            new_tickets=new_tickets,
            open_tickets=open_tickets,
        )
        self.clipboard_clear()
        self.clipboard_append(message)
        self.update()
        self.parent._show_toast("Mensaje copiado al portapapeles.")
        self.destroy()


class DailyReportTicketsModal(ctk.CTkToplevel):
    def __init__(self, parent: DailyReportModal, report_date: date) -> None:
        super().__init__(parent)
        self.parent = parent
        self.report_date = report_date
        self.include_vars: list[tk.BooleanVar] = []

        self.title("Tickets Del Reporte Diario")
        self.geometry("1160x620")
        self.minsize(940, 520)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        formatted_date = f"{report_date.day} {services.MONTHS_ES[report_date.month]} {report_date.year}"
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=f"Revision de tickets del reporte - {formatted_date}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        self.count_label = ctk.CTkLabel(header, text="")
        self.count_label.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 14))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            buttons,
            text="Restaurar Automatico",
            command=self._reset_automatic,
            fg_color="#52525b",
            hover_color="#3f3f46",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(buttons, text="Cerrar", command=self.destroy).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        _bind_modal_shortcuts(self, close_command=self.destroy)
        self._render_list()

    def _render_list(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.include_vars.clear()

        details = services.get_daily_report_ticket_details(self.report_date)
        included_count = sum(1 for ticket in details if ticket["included"])
        self.count_label.configure(text=f"Incluidos: {included_count} | Total disponibles: {len(details)}")
        self.parent._refresh_ticket_count()

        headers = ["Incluir", "Origen", "Fecha", "Ticket", "Mail", "Phone", "Estado", "Problema", "Estado Actual"]
        widths = [70, 145, 90, 135, 160, 105, 105, 190, 210]
        for column, title in enumerate(headers):
            ctk.CTkLabel(
                self.list_frame,
                text=title,
                width=widths[column],
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=column, sticky="w", padx=4, pady=(4, 8))

        if not details:
            ctk.CTkLabel(self.list_frame, text="No hay tickets registrados.").grid(
                row=1, column=0, columnspan=len(headers), sticky="w", padx=8, pady=16
            )
            return

        for row_index, ticket in enumerate(details, start=1):
            ticket_id = int(ticket["id"])
            include_var = tk.BooleanVar(value=bool(ticket["included"]))
            self.include_vars.append(include_var)
            ctk.CTkCheckBox(
                self.list_frame,
                text="",
                width=widths[0],
                variable=include_var,
                command=lambda tid=ticket_id, var=include_var: self._set_included(tid, var.get()),
            ).grid(row=row_index, column=0, sticky="w", padx=8, pady=4)

            origin = str(ticket["origin"])
            self._render_origin_badge(row_index, 1, widths[1], origin, bool(ticket["included"]))
            values = [
                ticket["fecha_creacion"],
                ticket.get("numero_ticket") or "-",
                ticket.get("mail") or "-",
                ticket.get("phone") or "-",
                ticket["estado"],
                ticket.get("problem_name") or "-",
                ticket["estado_actual"],
            ]
            text_color = None if ticket["included"] else "#a1a1aa"
            for column, value in enumerate(values, start=2):
                ctk.CTkLabel(
                    self.list_frame,
                    text=self.parent.parent._short_text(str(value), widths[column]),
                    width=widths[column],
                    anchor="w",
                    text_color=text_color,
                ).grid(row=row_index, column=column, sticky="w", padx=4, pady=4)

    def _set_included(self, ticket_id: int, included: bool) -> None:
        services.set_daily_report_ticket_included(self.report_date, ticket_id, included)
        self._render_list()
        self.parent.parent._show_toast("Seleccion del reporte actualizada.")

    def _render_origin_badge(self, row: int, column: int, width: int, origin: str, included: bool) -> None:
        colors = {
            "Creado hoy": ("#1d4ed8", "#dbeafe"),
            "Actualizado hoy": ("#166534", "#dcfce7"),
            "Creado y actualizado": ("#0f766e", "#ccfbf1"),
            "Cerrado hoy": ("#c2410c", "#ffedd5"),
            "Manual": ("#7c3aed", "#ede9fe"),
            "Fuera de regla": ("#3f3f46", "#e4e4e7"),
        }
        fg_color, text_color = colors.get(origin, colors["Fuera de regla"])
        if not included:
            fg_color, text_color = "#3f3f46", "#a1a1aa"
        ctk.CTkLabel(
            self.list_frame,
            text=self.parent.parent._short_text(origin, width),
            width=width,
            fg_color=fg_color,
            text_color=text_color,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=row, column=column, sticky="w", padx=4, pady=4)

    def _reset_automatic(self) -> None:
        confirmed = messagebox.askyesno(
            "Restaurar automatico",
            "Se eliminara la seleccion manual de esta fecha y se usara la regla automatica. Continuar?",
            parent=self,
        )
        if not confirmed:
            return
        services.reset_daily_report_ticket_overrides(self.report_date)
        self._render_list()
        self.parent.parent._show_toast("Seleccion automatica restaurada.")


class BulkTicketModal(ctk.CTkToplevel):
    def __init__(self, parent: TicketApp) -> None:
        super().__init__(parent)
        self.parent = parent
        self.tickets: list[str] = []
        self.problems: list[str] = []

        self.title("Crear Tickets Desde Lista")
        self.geometry("760x640")
        self.minsize(640, 520)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(self)
        controls.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        controls.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(controls, text="Pegar Tickets", command=lambda: self._paste_column("tickets")).grid(
            row=0, column=0, sticky="ew", padx=(8, 4), pady=10
        )
        ctk.CTkButton(controls, text="Pegar Problemas", command=lambda: self._paste_column("problems")).grid(
            row=0, column=1, sticky="ew", padx=4, pady=10
        )
        ctk.CTkButton(controls, text="Limpiar Lista", command=self._clear, fg_color="#52525b").grid(
            row=0, column=2, sticky="ew", padx=4, pady=10
        )
        ctk.CTkButton(controls, text="Guardar", command=self._save, fg_color="#16a34a", hover_color="#15803d").grid(
            row=0, column=3, sticky="ew", padx=(4, 8), pady=10
        )

        self.preview = ctk.CTkScrollableFrame(self, label_text="Vista previa")
        self.preview.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)

        self.result_label = ctk.CTkLabel(self, text="Pega una columna de Excel en Tickets y otra en Problemas.", anchor="w")
        self.result_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 14))

        _bind_modal_shortcuts(self, submit_command=self._save, close_command=self.destroy)
        self._render_preview()

    def _paste_column(self, target: str) -> None:
        try:
            clipboard = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("Portapapeles", "No hay texto disponible para pegar.", parent=self)
            return

        values = [line.strip() for line in clipboard.splitlines()]
        while values and not values[-1]:
            values.pop()

        if target == "tickets":
            self.tickets = values
        else:
            self.problems = values
        self._render_preview()

    def _clear(self) -> None:
        self.tickets = []
        self.problems = []
        self.result_label.configure(text="Lista limpia.")
        self._render_preview()

    def _render_preview(self) -> None:
        for widget in self.preview.winfo_children():
            widget.destroy()

        headers = ["#", "Ticket", "Problema", "Estado"]
        widths = [42, 190, 310, 140]
        for column, header in enumerate(headers):
            ctk.CTkLabel(
                self.preview,
                text=header,
                width=widths[column],
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=column, sticky="w", padx=4, pady=(6, 8))

        row_count = max(len(self.tickets), len(self.problems), 1)
        if not self.tickets and not self.problems:
            ctk.CTkLabel(self.preview, text="Sin datos pegados.").grid(
                row=1, column=0, columnspan=4, sticky="w", padx=4, pady=12
            )
            return

        for index in range(row_count):
            ticket = self.tickets[index].strip() if index < len(self.tickets) else ""
            problem = self.problems[index].strip() if index < len(self.problems) else ""
            status = self._preview_status(ticket)
            values = [str(index + 1), ticket or "-", problem or "-", status]
            for column, value in enumerate(values):
                ctk.CTkLabel(
                    self.preview,
                    text=self.parent._short_text(value, widths[column]),
                    width=widths[column],
                    anchor="w",
                    text_color="#f97316" if status == "Duplicado" else None,
                ).grid(row=index + 1, column=column, sticky="w", padx=4, pady=3)

        self.result_label.configure(
            text=f"Filas detectadas: {row_count} | Tickets: {len(self.tickets)} | Problemas: {len(self.problems)}"
        )

    def _preview_status(self, ticket: str) -> str:
        if not ticket:
            return "Sin ticket"
        if services.ticket_exists(ticket):
            return "Duplicado"
        return "Nuevo"

    def _save(self) -> None:
        if not self.tickets:
            messagebox.showwarning("Lista", "No hay tickets para guardar.", parent=self)
            return

        rows = []
        for index, ticket in enumerate(self.tickets):
            rows.append(
                {
                    "numero_ticket": ticket,
                    "problem_name": self.problems[index] if index < len(self.problems) else "",
                }
            )

        defaults = {
            "fecha_creacion": self.parent._selected_date().isoformat(),
            "pais": self.parent.pais_values[0] if self.parent.pais_values else "United States",
            "mail": "",
            "phone": "",
            "estado": "pendiente",
            "description": "",
            "estado_actual": self.parent.estado_actual_values[0]
            if self.parent.estado_actual_values
            else "Awaiting hq team response",
        }
        result = services.create_ticket_list(rows, defaults)
        created = result["created"]
        duplicates = result["duplicates"]
        ignored = result["ignored"]

        summary = [f"{len(created)} tickets adicionados."]
        if duplicates:
            summary.append(f"{len(duplicates)} tickets duplicados: {', '.join(duplicates)}")
        if ignored:
            summary.append(f"{len(ignored)} filas ignoradas sin ticket: {', '.join(map(str, ignored))}")

        self.result_label.configure(text=" | ".join(summary))
        messagebox.showinfo("Resultado", "\n".join(summary), parent=self)
        self.parent._load_tickets()
        self._render_preview()


class CreateTicketModal(ctk.CTkToplevel):
    def __init__(self, parent: TicketApp) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("Nuevo Ticket")
        self.geometry("720x680")
        self.minsize(620, 560)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.body = ctk.CTkScrollableFrame(self, label_text="Crear ticket")
        self.body.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.body.grid_columnconfigure((0, 1), weight=1)

        self.date_entry = self._date_entry(0, "Fecha", self.parent._selected_date())
        self.pais_combo = self._combo(0, 1, "Pais", self.parent.pais_values, self.parent.pais_values[0] if self.parent.pais_values else "")
        self.ticket_entry = self._entry(2, 0, "Numero Ticket", "")
        self.mail_entry = self._entry(2, 1, "Mail", "")
        self.phone_entry = self._entry(4, 0, "Phone", "")
        self.estado_combo = self._combo(4, 1, "Estado", list(services.get_estados()), "pendiente")
        self.problem_entry = self._entry(6, 0, "Problem Name", "", columnspan=2)
        self.estado_actual_combo = self._combo(
            8,
            0,
            "Estado Actual",
            self.parent.estado_actual_values,
            self.parent.estado_actual_values[0] if self.parent.estado_actual_values else "",
            columnspan=2,
        )

        ctk.CTkLabel(self.body, text="Descripcion").grid(row=10, column=0, columnspan=2, sticky="w", padx=10)
        self.description_text = ctk.CTkTextbox(self.body, height=140)
        self.description_text.grid(row=11, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 12))

        buttons = ctk.CTkFrame(self.body, fg_color="transparent")
        buttons.grid(row=12, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 14))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(buttons, text="Crear Ticket", command=self._save).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(buttons, text="Cancelar", command=self.destroy, fg_color="#52525b").grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        _bind_modal_shortcuts(self, submit_command=self._save, close_command=self.destroy, textboxes=(self.description_text,))
        self.after(100, self.ticket_entry.focus_set)

    def _entry(self, row: int, column: int, label: str, value: str, columnspan: int = 1) -> ctk.CTkEntry:
        ctk.CTkLabel(self.body, text=label).grid(row=row, column=column, columnspan=columnspan, sticky="w", padx=10)
        entry = ctk.CTkEntry(self.body)
        entry.grid(row=row + 1, column=column, columnspan=columnspan, sticky="ew", padx=10, pady=(4, 12))
        entry.insert(0, value)
        return entry

    def _combo(
        self,
        row: int,
        column: int,
        label: str,
        values: list[str],
        value: str,
        columnspan: int = 1,
    ) -> ctk.CTkComboBox:
        ctk.CTkLabel(self.body, text=label).grid(row=row, column=column, columnspan=columnspan, sticky="w", padx=10)
        combo_values = values + [ADD_NEW_OPTION] if label in {"Pais", "Estado Actual"} else values
        combo = ctk.CTkComboBox(
            self.body,
            values=combo_values,
            command=lambda selected, field=label: self._handle_dynamic_option(field, selected),
        )
        combo.grid(row=row + 1, column=column, columnspan=columnspan, sticky="ew", padx=10, pady=(4, 12))
        combo.set(value if value else (values[0] if values else ""))
        return combo

    def _date_entry(self, row: int, label: str, value: date) -> DateEntry:
        ctk.CTkLabel(self.body, text=label).grid(row=row, column=0, sticky="w", padx=10)
        entry = DateEntry(self.body, date_pattern="yyyy-mm-dd")
        entry.grid(row=row + 1, column=0, sticky="ew", padx=10, pady=(4, 12))
        entry.set_date(value)
        return entry

    def _handle_dynamic_option(self, field: str, selected: str) -> None:
        if selected != ADD_NEW_OPTION:
            return

        tipo = "pais" if field == "Pais" else "estado_actual"
        label = "pais" if tipo == "pais" else "estado actual"
        new_value = simpledialog.askstring("Nueva opcion", f"Ingresa nuevo {label}:", parent=self)
        if not new_value:
            self._reset_dynamic_combos()
            return

        try:
            saved_value = services.add_option(tipo, new_value)
        except ValueError as exc:
            messagebox.showerror("Dato invalido", str(exc), parent=self)
            self._reset_dynamic_combos()
            return

        self.parent._reload_dynamic_options()
        self.pais_combo.configure(values=self.parent.pais_values + [ADD_NEW_OPTION])
        self.estado_actual_combo.configure(values=self.parent.estado_actual_values + [ADD_NEW_OPTION])
        if tipo == "pais":
            self.pais_combo.set(saved_value)
        else:
            self.estado_actual_combo.set(saved_value)

    def _reset_dynamic_combos(self) -> None:
        if self.parent.pais_values:
            self.pais_combo.set(self.parent.pais_values[0])
        if self.parent.estado_actual_values:
            self.estado_actual_combo.set(self.parent.estado_actual_values[0])

    def _save(self) -> None:
        data = {
            "fecha_creacion": self.date_entry.get_date().isoformat(),
            "pais": self.pais_combo.get(),
            "numero_ticket": self.ticket_entry.get(),
            "mail": self.mail_entry.get(),
            "phone": self.phone_entry.get(),
            "estado": self.estado_combo.get(),
            "problem_name": self.problem_entry.get(),
            "description": self.description_text.get("1.0", "end").strip(),
            "estado_actual": self.estado_actual_combo.get(),
        }
        try:
            services.create_ticket(data)
        except ValueError as exc:
            messagebox.showerror("Datos invalidos", str(exc), parent=self)
            return

        self.parent._load_tickets()
        self.destroy()


class EditTicketModal(ctk.CTkToplevel):
    def __init__(self, parent: TicketApp, ticket_id: int) -> None:
        super().__init__(parent)
        self.parent = parent
        self.ticket_id = ticket_id
        self.ticket = services.get_ticket(ticket_id)
        if not self.ticket:
            messagebox.showerror("Ticket no encontrado", "No se encontro el ticket seleccionado.", parent=parent)
            self.destroy()
            return

        self.title(f"Editar Ticket #{ticket_id}")
        self.geometry("720x680")
        self.minsize(620, 560)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.body = ctk.CTkScrollableFrame(self, label_text="Informacion del ticket")
        self.body.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.body.grid_columnconfigure((0, 1), weight=1)

        self.date_entry = self._date_entry(0, "Fecha", str(self.ticket["fecha_creacion"]))
        self.pais_combo = self._combo(0, 1, "Pais", self.parent.pais_values, str(self.ticket["pais"]))
        self.ticket_entry = self._entry(2, 0, "Numero Ticket", str(self.ticket["numero_ticket"] or ""))
        self.mail_entry = self._entry(2, 1, "Mail", str(self.ticket["mail"] or ""))
        self.phone_entry = self._entry(4, 0, "Phone", str(self.ticket.get("phone") or ""))
        self.estado_combo = self._combo(4, 1, "Estado", list(services.get_estados()), str(self.ticket["estado"]))
        self.problem_entry = self._entry(6, 0, "Problem Name", str(self.ticket["problem_name"] or ""), columnspan=2)
        self.estado_actual_combo = self._combo(
            8,
            0,
            "Estado Actual",
            self.parent.estado_actual_values,
            str(self.ticket["estado_actual"]),
            columnspan=2,
        )

        ctk.CTkLabel(self.body, text="Descripcion").grid(row=10, column=0, columnspan=2, sticky="w", padx=10)
        self.description_text = ctk.CTkTextbox(self.body, height=140)
        self.description_text.grid(row=11, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 12))
        self.description_text.insert("1.0", str(self.ticket["description"] or ""))

        buttons = ctk.CTkFrame(self.body, fg_color="transparent")
        buttons.grid(row=12, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 14))
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(buttons, text="Guardar Cambios", command=self._save).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(buttons, text="Cancelar", command=self.destroy, fg_color="#52525b").grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        _bind_modal_shortcuts(self, submit_command=self._save, close_command=self.destroy, textboxes=(self.description_text,))
        self.after(100, self.ticket_entry.focus_set)

    def _entry(self, row: int, column: int, label: str, value: str, columnspan: int = 1) -> ctk.CTkEntry:
        ctk.CTkLabel(self.body, text=label).grid(row=row, column=column, columnspan=columnspan, sticky="w", padx=10)
        entry = ctk.CTkEntry(self.body)
        entry.grid(row=row + 1, column=column, columnspan=columnspan, sticky="ew", padx=10, pady=(4, 12))
        entry.insert(0, value)
        return entry

    def _combo(
        self,
        row: int,
        column: int,
        label: str,
        values: list[str],
        value: str,
        columnspan: int = 1,
    ) -> ctk.CTkComboBox:
        ctk.CTkLabel(self.body, text=label).grid(row=row, column=column, columnspan=columnspan, sticky="w", padx=10)
        combo_values = values + [ADD_NEW_OPTION] if label in {"Pais", "Estado Actual"} else values
        combo = ctk.CTkComboBox(
            self.body,
            values=combo_values,
            command=lambda selected, field=label: self._handle_dynamic_option(field, selected),
        )
        combo.grid(row=row + 1, column=column, columnspan=columnspan, sticky="ew", padx=10, pady=(4, 12))
        combo.set(value if value else (values[0] if values else ""))
        return combo

    def _date_entry(self, row: int, label: str, value: str) -> DateEntry:
        ctk.CTkLabel(self.body, text=label).grid(row=row, column=0, sticky="w", padx=10)
        entry = DateEntry(self.body, date_pattern="yyyy-mm-dd")
        entry.grid(row=row + 1, column=0, sticky="ew", padx=10, pady=(4, 12))
        entry.set_date(value)
        return entry

    def _handle_dynamic_option(self, field: str, selected: str) -> None:
        if selected != ADD_NEW_OPTION:
            return

        tipo = "pais" if field == "Pais" else "estado_actual"
        label = "pais" if tipo == "pais" else "estado actual"
        new_value = simpledialog.askstring("Nueva opcion", f"Ingresa nuevo {label}:", parent=self)
        if not new_value:
            self._reset_dynamic_combos()
            return

        try:
            saved_value = services.add_option(tipo, new_value)
        except ValueError as exc:
            messagebox.showerror("Dato invalido", str(exc), parent=self)
            self._reset_dynamic_combos()
            return

        self.parent._reload_dynamic_options()
        self.pais_combo.configure(values=self.parent.pais_values + [ADD_NEW_OPTION])
        self.estado_actual_combo.configure(values=self.parent.estado_actual_values + [ADD_NEW_OPTION])
        if tipo == "pais":
            self.pais_combo.set(saved_value)
        else:
            self.estado_actual_combo.set(saved_value)

    def _reset_dynamic_combos(self) -> None:
        self.pais_combo.set(str(self.ticket["pais"]))
        self.estado_actual_combo.set(str(self.ticket["estado_actual"]))

    def _save(self) -> None:
        data = {
            "fecha_creacion": self.date_entry.get_date().isoformat(),
            "pais": self.pais_combo.get(),
            "numero_ticket": self.ticket_entry.get(),
            "mail": self.mail_entry.get(),
            "phone": self.phone_entry.get(),
            "estado": self.estado_combo.get(),
            "problem_name": self.problem_entry.get(),
            "description": self.description_text.get("1.0", "end").strip(),
            "estado_actual": self.estado_actual_combo.get(),
        }
        try:
            services.update_ticket(self.ticket_id, data, status_change_date=self.parent._selected_date())
        except ValueError as exc:
            messagebox.showerror("Datos invalidos", str(exc), parent=self)
            return

        self.parent._load_tickets()
        self.destroy()


class CommentsModal(ctk.CTkToplevel):
    def __init__(self, parent: TicketApp, ticket_id: int) -> None:
        super().__init__(parent)
        self.parent = parent
        self.ticket_id = ticket_id
        self.title(f"Progreso Ticket #{ticket_id}")
        self.geometry("620x520")
        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ticket = services.get_ticket(ticket_id)
        ticket_number = str(ticket.get("numero_ticket") or ticket_id) if ticket else str(ticket_id)
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        ctk.CTkLabel(
            header,
            text=f"Comentarios - Ticket {ticket_number}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(header, text="Ctrl + Enter agrega el comentario", text_color="#a1a1aa").grid(
            row=1, column=0, sticky="w", padx=12, pady=(0, 10)
        )

        self.comments_frame = ctk.CTkScrollableFrame(self, label_text="Historial de comentarios")
        self.comments_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=8)

        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        input_frame.grid_columnconfigure(0, weight=1)

        self.comment_text = ctk.CTkTextbox(input_frame, height=90)
        self.comment_text.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(input_frame, text="Agregar Comentario", command=self._add_comment).grid(
            row=0, column=1, padx=(0, 8), pady=10
        )
        _bind_modal_shortcuts(self, submit_command=self._add_comment, close_command=self.destroy, textboxes=(self.comment_text,))
        self.after(100, self.comment_text.focus_set)
        self._load_comments()

    def _load_comments(self) -> None:
        for widget in self.comments_frame.winfo_children():
            widget.destroy()

        comments = services.get_comments(self.ticket_id)
        if not comments:
            ctk.CTkLabel(self.comments_frame, text="Sin comentarios registrados.").grid(
                row=0, column=0, sticky="w", padx=8, pady=8
            )
            return

        for row, comment in enumerate(comments):
            frame = ctk.CTkFrame(self.comments_frame)
            frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
            frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(frame, text=comment["fecha_hora"], font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, sticky="w", padx=10, pady=(8, 2)
            )
            ctk.CTkLabel(frame, text=comment["comentario"], wraplength=540, justify="left").grid(
                row=1, column=0, sticky="w", padx=10, pady=(0, 8)
            )

    def _add_comment(self) -> None:
        try:
            services.add_comment(self.ticket_id, self.comment_text.get("1.0", "end"))
        except ValueError as exc:
            messagebox.showerror("Comentario invalido", str(exc), parent=self)
            return
        self.comment_text.delete("1.0", "end")
        self.parent._load_tickets()
        self._load_comments()

class FloatingBadge(ctk.CTkToplevel):
    """Mini ventana flotante con conteo de tickets."""

    def __init__(self, parent: TicketApp) -> None:
        super().__init__(parent)
        self.parent = parent
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        w, h = 180, 56
        sw = self.winfo_screenwidth()
        self.geometry(f"{w}x{h}+{sw - w - 20}+80")

        self._drag_data: dict[str, int] = {"x": 0, "y": 0}

        frame = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=10)
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        frame.bind("<Button-1>", self._start_drag)
        frame.bind("<B1-Motion>", self._do_drag)

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(expand=True, padx=10, pady=8)
        inner.bind("<Button-1>", self._start_drag)
        inner.bind("<B1-Motion>", self._do_drag)

        self.main_label = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.main_label.pack()
        self.main_label.bind("<Button-1>", self._on_click)
        self.main_label.bind("<Button-3>", self._on_right_click)

        self.sub_label = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#a1a1aa",
        )
        self.sub_label.pack()
        self.sub_label.bind("<Button-1>", self._on_click)
        self.sub_label.bind("<Button-3>", self._on_right_click)

        self.protocol("WM_DELETE_WINDOW", self._hide)
        self.withdraw()

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _do_drag(self, event: tk.Event) -> None:
        dx = event.x_root - self._drag_data["x"]
        dy = event.y_root - self._drag_data["y"]
        x = self.winfo_x() + dx
        y = self.winfo_y() + dy
        self.geometry(f"+{x}+{y}")
        self._drag_data["x"] = event.x_root
        self._drag_data["y"] = event.y_root

    def _on_click(self, _event: tk.Event) -> None:
        self.parent.deiconify()
        self.parent.lift()
        self.parent.focus_force()

    def _on_right_click(self, _event: tk.Event) -> None:
        self._hide()

    def update_count(self, open_count: int, unupdated_count: int) -> None:
        if open_count == 0 and not self.winfo_viewable():
            return
        if open_count == 0:
            self.withdraw()
            return
        all_done = unupdated_count == 0
        self.main_label.configure(
            text=f"Tickets: {open_count}" + ("  (al dia)" if all_done else ""),
            text_color="#16a34a" if all_done else "#f4f4f5",
        )
        self.sub_label.configure(
            text="" if all_done else f"{unupdated_count} sin actualizar",
            text_color="#d97706",
        )
        self.deiconify()

    def _hide(self) -> None:
        self.withdraw()

    def toggle(self) -> None:
        if self.winfo_viewable():
            self.withdraw()
        else:
            self.deiconify()


if __name__ == "__main__":
    app = TicketApp()
    app.mainloop()
