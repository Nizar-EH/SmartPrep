from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QListWidget, QMessageBox
)

WEEKDAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


class ScheduleTemplateDialog(QDialog):
    """Gère l'emploi du temps type : pour chaque jour de la semaine, une liste
    d'heures + matières récurrentes, réutilisable chaque semaine."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Emploi du temps type")
        self.setMinimumSize(460, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Définis ici ton emploi du temps habituel. Tu pourras ensuite l'appliquer "
            "à n'importe quelle semaine en un clic depuis l'onglet Emploi du temps."
        ))

        form = QHBoxLayout()
        self.weekday_combo = QComboBox()
        self.weekday_combo.addItems(WEEKDAYS)
        self.weekday_combo.currentIndexChanged.connect(self._reload_list)
        form.addWidget(self.weekday_combo)

        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("Heure (ex: 08:00)")
        form.addWidget(self.time_input)

        self.subject_combo = QComboBox()
        for s in self.db.list_subjects():
            self.subject_combo.addItem(s["name"], s["id"])
        form.addWidget(self.subject_combo)
        layout.addLayout(form)

        add_btn = QPushButton("+ Ajouter ce créneau")
        add_btn.clicked.connect(self._add_entry)
        layout.addWidget(add_btn)

        layout.addWidget(QLabel("Créneaux du jour sélectionné :"))
        self.entries_list = QListWidget()
        layout.addWidget(self.entries_list)

        delete_btn = QPushButton("Supprimer le créneau sélectionné")
        delete_btn.clicked.connect(self._delete_entry)
        layout.addWidget(delete_btn)

        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._reload_list()

    def _add_entry(self):
        subject_id = self.subject_combo.currentData()
        if subject_id is None:
            QMessageBox.warning(self, "Aucune matière", "Ajoute d'abord une matière.")
            return
        time_text = self.time_input.text().strip()
        if not time_text:
            QMessageBox.warning(self, "Heure manquante", "Indique une heure (ex: 08:00).")
            return
        weekday = self.weekday_combo.currentIndex()
        self.db.add_template_entry(weekday, time_text, subject_id)
        self.time_input.clear()
        self._reload_list()

    def _reload_list(self):
        self.entries_list.clear()
        weekday = self.weekday_combo.currentIndex()
        self._entries = self.db.list_template_entries(weekday)
        for e in self._entries:
            self.entries_list.addItem(f"{e['start_time']} - {e['subject_name']}")

    def _delete_entry(self):
        row = self.entries_list.currentRow()
        if row < 0:
            return
        entry = self._entries[row]
        self.db.delete_template_entry(entry["id"])
        self._reload_list()
