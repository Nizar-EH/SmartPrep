from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QCheckBox, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt


class OnboardingDialog(QDialog):
    """Premier écran affiché à l'ouverture : nom, classe, matières + spécialités."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Bienvenue sur SchoolAI")
        self.setMinimumSize(480, 560)
        self.subject_rows = []  # (line_edit, checkbox_spe)

        layout = QVBoxLayout(self)

        title = QLabel("Bienvenue ! Configurons ton espace.")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Ton nom :"))
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Ta classe (ex : Terminale, 1ère, L2...) :"))
        self.classe_input = QLineEdit()
        layout.addWidget(self.classe_input)

        layout.addWidget(QLabel("Tes matières (coche 'spé' si c'est une spécialité) :"))
        self.subjects_container = QVBoxLayout()
        layout.addLayout(self.subjects_container)

        # quelques lignes de matière par défaut
        for _ in range(4):
            self._add_subject_row()

        add_btn = QPushButton("+ Ajouter une matière")
        add_btn.clicked.connect(self._add_subject_row)
        layout.addWidget(add_btn)

        layout.addStretch()

        validate_btn = QPushButton("Commencer")
        validate_btn.setStyleSheet(
            "font-weight: bold; padding: 8px; background-color: #2563eb; color: white; border-radius: 6px;"
        )
        validate_btn.clicked.connect(self._on_validate)
        layout.addWidget(validate_btn)

    def _add_subject_row(self):
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Nom de la matière")
        spe_check = QCheckBox("Spé")
        row.addWidget(name_edit)
        row.addWidget(spe_check)
        self.subjects_container.addWidget(row_widget)
        self.subject_rows.append((name_edit, spe_check))

    def _on_validate(self):
        name = self.name_input.text().strip()
        classe = self.classe_input.text().strip()

        if not name or not classe:
            QMessageBox.warning(self, "Champs manquants", "Merci de renseigner ton nom et ta classe.")
            return

        subjects = [(edit.text().strip(), check.isChecked())
                    for edit, check in self.subject_rows if edit.text().strip()]

        if not subjects:
            QMessageBox.warning(self, "Matières manquantes", "Ajoute au moins une matière.")
            return

        self.db.save_profile(name, classe)
        for subject_name, is_spe in subjects:
            self.db.add_subject(subject_name, is_spe)

        self.accept()
