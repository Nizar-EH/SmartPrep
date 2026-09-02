from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit,
    QPushButton, QListWidget, QDateEdit, QLineEdit, QMessageBox,
    QTableWidget, QTableWidgetItem, QTabWidget
)
from PyQt6.QtCore import QDate

from ui.schedule_template_dialog import ScheduleTemplateDialog, WEEKDAYS


class ScheduleTab(QWidget):
    """Permet de 'nourrir' l'IA au fil de la journée : à chaque heure, on note
    ce qui a été fait en cours. Propose aussi un emploi du temps type
    réutilisable chaque semaine et une vue calendrier hebdomadaire."""

    def __init__(self, db):
        super().__init__()
        self.db = db

        outer = QVBoxLayout(self)
        title = QLabel("Emploi du temps interactif")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        outer.addWidget(title)

        sub_tabs = QTabWidget()
        outer.addWidget(sub_tabs)

        # ---------- Sous-onglet : saisie journalière ----------
        day_widget = QWidget()
        layout = QVBoxLayout(day_widget)
        layout.addWidget(QLabel(
            "Ajoute une entrée à chaque heure de cours pour que l'IA sache ce que vous avez fait."
        ))

        template_row = QHBoxLayout()
        template_btn = QPushButton("⚙️ Gérer l'emploi du temps type")
        template_btn.clicked.connect(self._open_template_dialog)
        template_row.addWidget(template_btn)

        apply_template_btn = QPushButton("📥 Appliquer le modèle à ce jour")
        apply_template_btn.clicked.connect(self._apply_template)
        template_row.addWidget(apply_template_btn)

        duplicate_btn = QPushButton("⏮ Dupliquer la structure d'hier")
        duplicate_btn.clicked.connect(self._duplicate_yesterday)
        template_row.addWidget(duplicate_btn)
        layout.addLayout(template_row)

        form = QHBoxLayout()
        self.date_input = QDateEdit(calendarPopup=True)
        self.date_input.setDate(QDate.currentDate())
        form.addWidget(self.date_input)

        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("Heure (ex: 08:00)")
        form.addWidget(self.time_input)

        self.subject_combo = QComboBox()
        self._reload_subjects()
        form.addWidget(self.subject_combo)
        layout.addLayout(form)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("Qu'avez-vous fait pendant cette heure ?")
        self.content_input.setFixedHeight(100)
        layout.addWidget(self.content_input)

        add_btn = QPushButton("Ajouter au journal de cours")
        add_btn.clicked.connect(self._add_entry)
        layout.addWidget(add_btn)

        layout.addWidget(QLabel("Entrées du jour sélectionné (double-clique pour compléter le contenu) :"))
        self.entries_list = QListWidget()
        self.entries_list.itemDoubleClicked.connect(self._edit_entry_content)
        layout.addWidget(self.entries_list)

        self.date_input.dateChanged.connect(self._reload_entries)
        self.date_input.dateChanged.connect(self._reload_week_view)

        sub_tabs.addTab(day_widget, "Saisie du jour")

        # ---------- Sous-onglet : vue calendrier hebdomadaire ----------
        week_widget = QWidget()
        week_layout = QVBoxLayout(week_widget)
        week_layout.addWidget(QLabel(
            "Vue de la semaine contenant la date sélectionnée dans l'onglet 'Saisie du jour'. "
            "Clique sur une case pour aller directement à ce jour."
        ))
        self.week_table = QTableWidget()
        self.week_table.setColumnCount(7)
        self.week_table.setHorizontalHeaderLabels(WEEKDAYS)
        self.week_table.cellClicked.connect(self._on_week_cell_clicked)
        week_layout.addWidget(self.week_table)
        sub_tabs.addTab(week_widget, "Vue semaine")

        sub_tabs.currentChanged.connect(lambda i: self._reload_week_view() if i == 1 else None)

        self._reload_entries()
        self._reload_week_view()

    # ---------- saisie journalière ----------
    def _reload_subjects(self):
        self.subject_combo.clear()
        for s in self.db.list_subjects():
            self.subject_combo.addItem(s["name"], s["id"])

    def _add_entry(self):
        subject_id = self.subject_combo.currentData()
        if subject_id is None:
            QMessageBox.warning(self, "Aucune matière", "Ajoute d'abord une matière dans les paramètres.")
            return
        time_text = self.time_input.text().strip() or "00:00"
        content = self.content_input.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Contenu vide", "Décris ce qui a été fait pendant cette heure.")
            return

        date_str = self.date_input.date().toString("yyyy-MM-dd")
        self.db.add_schedule_entry(date_str, time_text, subject_id, content)
        self.content_input.clear()
        self.time_input.clear()
        self._reload_entries()
        self._reload_week_view()

    def _reload_entries(self):
        self.entries_list.clear()
        date_str = self.date_input.date().toString("yyyy-MM-dd")
        self._entries_today = self.db.get_schedule_for_date(date_str)
        for e in self._entries_today:
            marker = "" if e["content_text"] else " (à compléter)"
            self.entries_list.addItem(f"{e['start_time']} - {e['subject_name']} : {e['content_text']}{marker}")

    def _edit_entry_content(self, item):
        """Permet de compléter le contenu d'une entrée créée via le modèle ou
        la duplication (initialement vide)."""
        idx = self.entries_list.row(item)
        entry = self._entries_today[idx]
        from PyQt6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getMultiLineText(
            self, "Compléter le contenu", f"{entry['start_time']} - {entry['subject_name']}",
            entry["content_text"] or ""
        )
        if ok:
            # on ré-utilise add_schedule_entry en écrasant simplement via une
            # requête directe pour rester simple
            self.db.conn.execute(
                "UPDATE schedule_entries SET content_text = ? WHERE id = ?", (text, entry["id"])
            )
            self.db.conn.commit()
            self._reload_entries()
            self._reload_week_view()

    # ---------- modèle hebdomadaire ----------
    def _open_template_dialog(self):
        dialog = ScheduleTemplateDialog(self.db, self)
        dialog.exec()

    def _apply_template(self):
        date_str = self.date_input.date().toString("yyyy-MM-dd")
        weekday = self.date_input.date().dayOfWeek() - 1  # Qt: 1=Lundi -> 0=Lundi
        created = self.db.apply_template_to_date(date_str, weekday)
        if created == 0:
            QMessageBox.information(self, "Rien à ajouter",
                                     "Aucun nouveau créneau du modèle à ajouter (déjà présents, ou modèle vide "
                                     "pour ce jour — configure-le via 'Gérer l'emploi du temps type').")
        else:
            QMessageBox.information(self, "Modèle appliqué", f"{created} créneau(x) ajouté(s). Complète leur contenu au fil des cours.")
        self._reload_entries()
        self._reload_week_view()

    def _duplicate_yesterday(self):
        target_date = self.date_input.date()
        source_date = target_date.addDays(-1)
        created = self.db.duplicate_day_structure(
            source_date.toString("yyyy-MM-dd"), target_date.toString("yyyy-MM-dd")
        )
        if created == 0:
            QMessageBox.information(self, "Rien à dupliquer",
                                     "Aucun nouveau créneau à copier depuis le jour précédent.")
        else:
            QMessageBox.information(self, "Structure dupliquée", f"{created} créneau(x) copié(s). Complète leur contenu.")
        self._reload_entries()
        self._reload_week_view()

    # ---------- vue semaine ----------
    def _reload_week_view(self):
        selected = self.date_input.date()
        # Lundi de la semaine contenant 'selected'
        weekday = selected.dayOfWeek()  # 1=Lundi..7=Dimanche
        monday = selected.addDays(-(weekday - 1))
        week_dates = [monday.addDays(i) for i in range(7)]

        start_str = week_dates[0].toString("yyyy-MM-dd")
        end_str = week_dates[-1].toString("yyyy-MM-dd")
        entries = self.db.get_schedule_for_range(start_str, end_str)

        by_date = {}
        for e in entries:
            by_date.setdefault(e["date"], []).append(e)

        self.week_table.setHorizontalHeaderLabels(
            [f"{WEEKDAYS[i]}\n{week_dates[i].toString('dd/MM')}" for i in range(7)]
        )

        max_rows = max((len(v) for v in by_date.values()), default=1)
        self.week_table.setRowCount(max(max_rows, 1))
        self.week_table.clearContents()

        self._week_dates = week_dates
        for col, d in enumerate(week_dates):
            day_entries = sorted(by_date.get(d.toString("yyyy-MM-dd"), []), key=lambda e: e["start_time"])
            for row, e in enumerate(day_entries):
                snippet = (e["content_text"] or "(à compléter)")[:40]
                item = QTableWidgetItem(f"{e['start_time']} {e['subject_name']}\n{snippet}")
                self.week_table.setItem(row, col, item)

        self.week_table.resizeRowsToContents()

    def _on_week_cell_clicked(self, row, col):
        if hasattr(self, "_week_dates") and col < len(self._week_dates):
            self.date_input.setDate(self._week_dates[col])

    def refresh(self):
        self._reload_subjects()
        self._reload_entries()
        self._reload_week_view()
