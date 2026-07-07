from __future__ import annotations

from datetime import date, timedelta
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk
from tkcalendar import DateEntry

import services
from database import DB_PATH, initialize_database


ADD_NEW_OPTION = "<Añadir Nuevo...>"


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
        self.table_columns = self._default_table_columns()
        self.header_drag: dict[str, object] | None = None

        self._build_layout()
        self._reload_dynamic_options()
        self._load_tickets()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(self, corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        top_bar.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(top_bar, text="Fecha:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(16, 8), pady=12
        )
        self.date_entry = DateEntry(top_bar, date_pattern="yyyy-mm-dd", width=14)
        self.date_entry.set_date(date.today())
        self.date_entry.grid(row=0, column=1, padx=8, pady=12)
        self.date_entry.bind("<<DateEntrySelected>>", lambda _event: self._load_tickets())

        ctk.CTkButton(
            top_bar,
            text="<",
            width=42,
            command=lambda: self._change_selected_day(-1),
        ).grid(row=1, column=1, sticky="w", padx=(8, 2), pady=(0, 10))
        ctk.CTkButton(
            top_bar,
            text=">",
            width=42,
            command=lambda: self._change_selected_day(1),
        ).grid(row=1, column=1, sticky="e", padx=(2, 8), pady=(0, 10))

        ctk.CTkButton(top_bar, text="Cargar Fecha", command=self._load_tickets).grid(
            row=0, column=2, padx=8, pady=12
        )
        ctk.CTkButton(
            top_bar,
            text="Nuevo Ticket",
            command=self._open_create_modal,
            fg_color="#16a34a",
            hover_color="#15803d",
        ).grid(row=0, column=3, padx=8, pady=12)
        ctk.CTkButton(
            top_bar,
            text="Lista",
            command=self._open_bulk_modal,
            fg_color="#0891b2",
            hover_color="#0e7490",
            width=90,
        ).grid(row=1, column=3, padx=8, pady=(0, 10))
        ctk.CTkButton(
            top_bar,
            text="Defecto",
            command=self._reset_table_columns,
            fg_color="#52525b",
            hover_color="#3f3f46",
            width=90,
        ).grid(row=1, column=5, padx=(8, 4), pady=(0, 10))
        ctk.CTkButton(top_bar, text="Exportar DB", command=self._export_database, width=105).grid(
            row=0, column=5, padx=(8, 4), pady=12
        )
        ctk.CTkButton(top_bar, text="Importar DB", command=self._import_database, width=105).grid(
            row=0, column=6, padx=4, pady=12
        )
        ctk.CTkButton(
            top_bar,
            text="Actualizar Tabla",
            command=self._load_tickets,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
        ).grid(row=0, column=7, padx=(4, 6), pady=12)
        ctk.CTkButton(
            top_bar,
            text="Generar Reporte SMS",
            command=self._copy_sms_report,
            fg_color="#d97706",
            hover_color="#b45309",
        ).grid(row=0, column=8, padx=(6, 16), pady=12)

        self.table_container = ctk.CTkFrame(self)
        self.table_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        self.table_container.grid_columnconfigure(0, weight=1)
        self.table_container.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.table_container,
            text="Tickets visibles",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self.table_canvas = tk.Canvas(self.table_container, highlightthickness=0, bg="#242424")
        self.table_canvas.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 10))

        self.table_v_scroll = ctk.CTkScrollbar(
            self.table_container,
            orientation="vertical",
            command=self.table_canvas.yview,
        )
        self.table_v_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 10))

        self.table_h_scroll = ctk.CTkScrollbar(
            self.table_container,
            orientation="horizontal",
            command=self.table_canvas.xview,
        )
        self.table_h_scroll.grid(row=2, column=0, sticky="ew", padx=(10, 0), pady=(0, 10))

        self.table_canvas.configure(
            xscrollcommand=self.table_h_scroll.set,
            yscrollcommand=self.table_v_scroll.set,
        )
        self.grid_frame = ctk.CTkFrame(self.table_canvas, fg_color="transparent")
        self.table_window = self.table_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", self._update_table_scrollregion)
        self.table_canvas.bind("<Configure>", self._sync_table_height)
        self.table_canvas.bind_all("<MouseWheel>", self._on_table_mousewheel)

    def _default_table_columns(self) -> list[dict[str, object]]:
        return [
            {"key": "number", "title": "#", "width": 36},
            {"key": "days", "title": "Dias", "width": 48},
            {"key": "fecha", "title": "Fecha", "width": 72},
            {"key": "pais", "title": "Pais", "width": 80},
            {"key": "ticket", "title": "Ticket", "width": 118},
            {"key": "mail", "title": "Mail", "width": 125},
            {"key": "phone", "title": "Phone", "width": 90},
            {"key": "estado", "title": "Estado", "width": 112},
            {"key": "problem", "title": "Problema", "width": 135},
            {"key": "estado_actual", "title": "Estado Actual", "width": 145},
            {"key": "actions", "title": "Opciones", "width": 150},
        ]

    def _update_table_scrollregion(self, _event: tk.Event | None = None) -> None:
        self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all"))

    def _sync_table_height(self, event: tk.Event) -> None:
        self.table_canvas.itemconfigure(self.table_window, height=event.height)

    def _on_table_mousewheel(self, event: tk.Event) -> None:
        widget = self.table_canvas.winfo_containing(event.x_root, event.y_root)
        if not self._is_table_widget(widget):
            return
        self.table_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _is_table_widget(self, widget: tk.Widget | None) -> bool:
        while widget is not None:
            if widget == self.table_container:
                return True
            widget = widget.master
        return False

    def _open_create_modal(self) -> None:
        CreateTicketModal(self)

    def _open_bulk_modal(self) -> None:
        BulkTicketModal(self)

    def _reset_table_columns(self) -> None:
        self.table_columns = self._default_table_columns()
        self._render_ticket_grid()

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
        self._render_ticket_grid()

    def _render_ticket_grid(self) -> None:
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        for column, config in enumerate(self.table_columns):
            self._render_header(column, config)

        if not self.visible_tickets:
            ctk.CTkLabel(self.grid_frame, text="No hay tickets para la fecha seleccionada.").grid(
                row=1, column=0, columnspan=len(self.table_columns), sticky="w", padx=8, pady=20
            )
            return

        for row_index, ticket in enumerate(self.visible_tickets, start=1):
            text_color = "#f97316" if ticket.get("is_rollover") else None
            days_open = self._days_open(str(ticket["fecha_creacion"]))
            row_values = {
                "number": row_index,
                "days": days_open,
                "fecha": ticket["fecha_creacion"],
                "pais": ticket["pais"],
                "mail": ticket["mail"],
                "phone": ticket.get("phone", ""),
                "problem": ticket["problem_name"],
            }
            for column, config in enumerate(self.table_columns):
                key = str(config["key"])
                width = int(config["width"])
                if key == "ticket":
                    self._render_ticket_button(row_index, column, width, ticket)
                elif key == "actions":
                    self._render_actions(row_index, column, width, ticket)
                elif key == "estado":
                    self._render_estado_combo(row_index, column, width, ticket)
                elif key == "estado_actual":
                    self._render_estado_actual_combo(row_index, column, width, ticket)
                else:
                    self._render_text_cell(
                        row_index,
                        column,
                        width,
                        str(row_values.get(key, "") or "-"),
                        str(config["title"]),
                        text_color,
                    )

    def _render_header(self, column: int, config: dict[str, object]) -> None:
        width = int(config["width"])
        title = str(config["title"])
        label = ctk.CTkLabel(
            self.grid_frame,
            text=f"{title}  |",
            width=width,
            anchor="w",
            font=ctk.CTkFont(weight="bold"),
        )
        label.grid(row=0, column=column, sticky="w", padx=3, pady=(6, 8))
        label.bind("<ButtonPress-1>", lambda event, key=config["key"]: self._start_header_drag(event, str(key)))
        label.bind("<Motion>", lambda event, widget=label: self._set_header_cursor(event, widget))

    def _render_text_cell(
        self,
        row: int,
        column: int,
        width: int,
        full_text: str,
        title: str,
        text_color: str | None,
    ) -> None:
        cell = ctk.CTkLabel(
            self.grid_frame,
            text=self._short_text(full_text, width),
            text_color=text_color,
            anchor="w",
            width=width,
        )
        cell.grid(row=row, column=column, sticky="w", padx=3, pady=4)
        cell.bind("<Button-1>", lambda _event, cell_title=title, text=full_text: self._show_cell_text(cell_title, text))

    def _render_ticket_button(self, row: int, column: int, width: int, ticket: dict[str, object]) -> None:
        ticket_cell = ctk.CTkFrame(self.grid_frame, fg_color="transparent", width=width, height=28)
        ticket_cell.grid(row=row, column=column, sticky="w", padx=3, pady=3)
        ticket_cell.grid_propagate(False)
        ticket_cell.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            ticket_cell,
            text=self._short_text(str(ticket["numero_ticket"] or "Progreso"), width),
            width=width,
            height=24,
            command=lambda ticket_id=int(ticket["id"]): self._open_comments_modal(ticket_id),
        ).grid(row=0, column=0, sticky="ew")

    def _render_actions(self, row: int, column: int, width: int, ticket: dict[str, object]) -> None:
        actions_cell = ctk.CTkFrame(self.grid_frame, fg_color="transparent", width=width, height=28)
        actions_cell.grid(row=row, column=column, sticky="e", padx=3, pady=3)
        actions_cell.grid_propagate(False)
        edit_width = max(56, min(70, (width - 8) // 2))
        delete_width = max(64, width - edit_width - 4)
        ctk.CTkButton(
            actions_cell,
            text="Editar",
            width=edit_width,
            height=24,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=lambda ticket_id=int(ticket["id"]): self._open_edit_modal(ticket_id),
        ).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(
            actions_cell,
            text="Eliminar",
            width=delete_width,
            height=24,
            fg_color="#dc2626",
            hover_color="#991b1b",
            command=lambda ticket_id=int(ticket["id"]): self._delete_ticket(ticket_id),
        ).grid(row=0, column=1)

    def _render_estado_combo(self, row: int, column: int, width: int, ticket: dict[str, object]) -> None:
        estado_combo = ctk.CTkComboBox(
            self.grid_frame,
            values=list(services.get_estados()),
            width=width,
            command=lambda value, ticket_id=int(ticket["id"]): self._update_ticket_estado(ticket_id, value),
        )
        estado_combo.set(str(ticket["estado"]))
        estado_combo.grid(row=row, column=column, sticky="w", padx=3, pady=4)

    def _render_estado_actual_combo(self, row: int, column: int, width: int, ticket: dict[str, object]) -> None:
        estado_actual_combo = ctk.CTkComboBox(
            self.grid_frame,
            values=self.estado_actual_values,
            width=width,
            command=lambda value, ticket_id=int(ticket["id"]): self._update_ticket_estado_actual(ticket_id, value),
        )
        estado_actual_combo.set(str(ticket["estado_actual"]))
        estado_actual_combo.grid(row=row, column=column, sticky="w", padx=3, pady=4)

    def _start_header_drag(self, event: tk.Event, key: str) -> None:
        config = self._column_config(key)
        if not config:
            return
        widget_width = max(int(config["width"]), event.widget.winfo_width())
        mode = "resize" if event.x >= widget_width - 12 else "move"
        self.header_drag = {
            "key": key,
            "mode": mode,
            "x_root": event.x_root,
            "start_width": int(config["width"]),
            "widget": event.widget,
        }

        self.bind("<B1-Motion>", self._drag_header)
        self.bind("<ButtonRelease-1>", self._finish_header_drag)

    def _set_header_cursor(self, event: tk.Event, widget: tk.Widget) -> None:
        cursor = "sb_h_double_arrow" if event.x >= widget.winfo_width() - 12 else "fleur"
        try:
            widget.configure(cursor=cursor)
        except Exception:
            pass

    def _drag_header(self, event: tk.Event) -> None:
        if not self.header_drag or self.header_drag["mode"] != "resize":
            return

        key = str(self.header_drag["key"])
        config = self._column_config(key)
        if not config:
            return

        delta = event.x_root - int(self.header_drag["x_root"])
        new_width = max(34, int(self.header_drag["start_width"]) + delta)
        config["width"] = new_width
        widget = self.header_drag.get("widget")
        if widget:
            widget.configure(width=new_width)

    def _finish_header_drag(self, event: tk.Event) -> None:
        if not self.header_drag:
            return
        key = str(self.header_drag["key"])
        mode = str(self.header_drag["mode"])
        delta = event.x_root - int(self.header_drag["x_root"])
        if mode == "resize":
            config = self._column_config(key)
            if config:
                config["width"] = max(34, int(self.header_drag["start_width"]) + delta)
        elif abs(delta) >= 45:
            self._move_column_by_delta(key, delta)
        self.header_drag = None
        self.unbind("<B1-Motion>")
        self.unbind("<ButtonRelease-1>")
        self._render_ticket_grid()

    def _column_config(self, key: str) -> dict[str, object] | None:
        return next((column for column in self.table_columns if column["key"] == key), None)

    def _move_column_by_delta(self, key: str, delta: int) -> None:
        current_index = next((index for index, column in enumerate(self.table_columns) if column["key"] == key), None)
        if current_index is None:
            return
        step = max(1, abs(delta) // 90)
        target_index = current_index + (step if delta > 0 else -step)
        target_index = max(0, min(len(self.table_columns) - 1, target_index))
        if target_index == current_index:
            return
        column = self.table_columns.pop(current_index)
        self.table_columns.insert(target_index, column)

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

    def _show_cell_text(self, title: str, text: str) -> None:
        if text == "-":
            return
        messagebox.showinfo(title, text, parent=self)

    def _delete_ticket(self, ticket_id: int) -> None:
        confirmed = messagebox.askyesno(
            "Eliminar ticket",
            "Esta accion eliminara permanentemente el ticket y sus comentarios. Continuar?",
            parent=self,
        )
        if not confirmed:
            return
        services.delete_ticket(ticket_id)
        self._load_tickets()

    def _update_ticket_estado(self, ticket_id: int, estado: str) -> None:
        try:
            services.update_ticket_estado(ticket_id, estado)
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
            services.update_ticket(self.ticket_id, data)
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
        self.grid_rowconfigure(0, weight=1)

        self.comments_frame = ctk.CTkScrollableFrame(self, label_text="Historial de comentarios")
        self.comments_frame.grid(row=0, column=0, sticky="nsew", padx=14, pady=(14, 8))

        input_frame = ctk.CTkFrame(self)
        input_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        input_frame.grid_columnconfigure(0, weight=1)

        self.comment_text = ctk.CTkTextbox(input_frame, height=90)
        self.comment_text.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(input_frame, text="Agregar Comentario", command=self._add_comment).grid(
            row=0, column=1, padx=(0, 10), pady=10
        )

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
        self._load_comments()


if __name__ == "__main__":
    app = TicketApp()
    app.mainloop()
