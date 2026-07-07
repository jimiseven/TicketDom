from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import messagebox, simpledialog

import customtkinter as ctk
from tkcalendar import DateEntry

import services
from database import initialize_database


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
        self.form_visible = True

        self._build_layout()
        self._reload_dynamic_options()
        self._clear_form()
        self._load_tickets()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(self, corner_radius=0)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        top_bar.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(top_bar, text="Fecha:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(16, 8), pady=12
        )
        self.date_entry = DateEntry(top_bar, date_pattern="yyyy-mm-dd", width=14)
        self.date_entry.set_date(date.today())
        self.date_entry.grid(row=0, column=1, padx=8, pady=12)
        self.date_entry.bind("<<DateEntrySelected>>", lambda _event: self._load_tickets())

        ctk.CTkButton(top_bar, text="Cargar Fecha", command=self._load_tickets).grid(
            row=0, column=2, padx=8, pady=12
        )
        self.toggle_form_button = ctk.CTkButton(
            top_bar,
            text="Ocultar Creacion",
            command=self._toggle_form_panel,
            fg_color="#52525b",
            hover_color="#3f3f46",
        )
        self.toggle_form_button.grid(row=0, column=3, padx=8, pady=12)
        ctk.CTkButton(
            top_bar,
            text="Actualizar Tabla",
            command=self._load_tickets,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
        ).grid(row=0, column=5, padx=(8, 6), pady=12)
        ctk.CTkButton(
            top_bar,
            text="Generar Reporte SMS",
            command=self._copy_sms_report,
            fg_color="#d97706",
            hover_color="#b45309",
        ).grid(row=0, column=6, padx=(6, 16), pady=12)

        self.form_frame = ctk.CTkScrollableFrame(self, width=330, label_text="Crear Ticket")
        self.form_frame.grid(row=1, column=0, sticky="nsw", padx=12, pady=12)

        self.table_container = ctk.CTkFrame(self)
        self.table_container.grid(row=1, column=1, sticky="nsew", padx=(0, 12), pady=12)
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

        self._build_form()

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

    def _toggle_form_panel(self) -> None:
        if self.form_visible:
            self.form_frame.grid_remove()
            self.toggle_form_button.configure(text="Mostrar Creacion")
            self.form_visible = False
        else:
            self.form_frame.grid(row=1, column=0, sticky="nsw", padx=12, pady=12)
            self.toggle_form_button.configure(text="Ocultar Creacion")
            self.form_visible = True

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
        self.pais_combo.configure(values=self.pais_values + [ADD_NEW_OPTION])
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
        if self.pais_values:
            self.pais_combo.set(self.pais_values[0])
        if self.estado_actual_values:
            self.estado_actual_combo.set(self.estado_actual_values[0])

    def _selected_date(self) -> date:
        return self.date_entry.get_date()

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

        headers = ["Fecha", "Pais", "Ticket", "Mail", "Phone", "Estado", "Problema", "Estado Actual"]
        widths = [72, 80, 118, 125, 90, 112, 135, 145]
        for column, header in enumerate(headers):
            ctk.CTkLabel(
                self.grid_frame,
                text=header,
                width=widths[column],
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            ).grid(
                row=0, column=column, sticky="w", padx=3, pady=(6, 8)
            )

        if not self.visible_tickets:
            ctk.CTkLabel(self.grid_frame, text="No hay tickets para la fecha seleccionada.").grid(
                row=1, column=0, columnspan=len(headers), sticky="w", padx=8, pady=20
            )
            return

        for row_index, ticket in enumerate(self.visible_tickets, start=1):
            text_color = "#f97316" if ticket.get("is_rollover") else None
            values = [
                (0, ticket["fecha_creacion"]),
                (1, ticket["pais"]),
                (3, ticket["mail"]),
                (4, ticket.get("phone", "")),
                (6, ticket["problem_name"]),
                (7, ticket["estado_actual"]),
            ]
            for target_column, value in values:
                full_text = str(value or "-")
                cell = ctk.CTkLabel(
                    self.grid_frame,
                    text=self._short_text(full_text, widths[target_column]),
                    text_color=text_color,
                    anchor="w",
                    width=widths[target_column],
                )
                cell.grid(row=row_index, column=target_column, sticky="w", padx=3, pady=4)
                cell.bind(
                    "<Button-1>",
                    lambda _event, title=headers[target_column], text=full_text: self._show_cell_text(title, text),
                )

            ticket_cell = ctk.CTkFrame(self.grid_frame, fg_color="transparent", width=widths[2], height=92)
            ticket_cell.grid(row=row_index, column=2, sticky="w", padx=3, pady=3)
            ticket_cell.grid_propagate(False)
            ticket_cell.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(
                ticket_cell,
                text=self._short_text(str(ticket["numero_ticket"] or "Progreso"), widths[2]),
                width=widths[2],
                height=24,
                command=lambda ticket_id=int(ticket["id"]): self._open_comments_modal(ticket_id),
            ).grid(row=0, column=0, sticky="ew", pady=(0, 3))
            ctk.CTkButton(
                ticket_cell,
                text="Editar",
                width=widths[2],
                height=24,
                fg_color="#16a34a",
                hover_color="#15803d",
                command=lambda ticket_id=int(ticket["id"]): self._open_edit_modal(ticket_id),
            ).grid(row=1, column=0, sticky="ew", pady=(0, 3))
            ctk.CTkButton(
                ticket_cell,
                text="Eliminar",
                width=widths[2],
                height=24,
                fg_color="#dc2626",
                hover_color="#991b1b",
                command=lambda ticket_id=int(ticket["id"]): self._delete_ticket(ticket_id),
            ).grid(row=2, column=0, sticky="ew")

            estado_combo = ctk.CTkComboBox(
                self.grid_frame,
                values=list(services.get_estados()),
                width=widths[5],
                command=lambda value, ticket_id=int(ticket["id"]): self._update_ticket_estado(ticket_id, value),
            )
            estado_combo.set(str(ticket["estado"]))
            estado_combo.grid(row=row_index, column=5, sticky="w", padx=3, pady=4)

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
