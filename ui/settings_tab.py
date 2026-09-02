import shutil

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
    QHBoxLayout, QFileDialog, QGroupBox
)
import config
import db as db_module


class SettingsTab(QWidget):
    """Configuration locale : clé API Gemini + sauvegarde/restauration des données."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Paramètres")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(QLabel(
            "Clé API Google Gemini (gratuite, récupérable sur aistudio.google.com/app/apikey).\n"
            "Elle est stockée uniquement en local dans ~/.schoolai/config.json, jamais envoyée ailleurs."
        ))

        row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setText(config.get_api_key())
        row.addWidget(self.key_input)

        self.show_btn = QPushButton("Afficher")
        self.show_btn.clicked.connect(self._toggle_visibility)
        row.addWidget(self.show_btn)
        layout.addLayout(row)

        save_btn = QPushButton("Enregistrer")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        # ---------- sauvegarde / restauration des données ----------
        backup_box = QGroupBox("Sauvegarde de tes données")
        backup_layout = QVBoxLayout(backup_box)
        backup_layout.addWidget(QLabel(
            "Toutes tes données (fiches, notes, exercices, emploi du temps...) sont "
            "dans un seul fichier local. Exporte-le pour le garder en sécurité ou "
            "le transférer sur un autre ordinateur."
        ))

        backup_row = QHBoxLayout()
        export_btn = QPushButton("📤 Exporter mes données")
        export_btn.clicked.connect(self._export_backup)
        backup_row.addWidget(export_btn)

        import_btn = QPushButton("📥 Importer une sauvegarde")
        import_btn.clicked.connect(self._import_backup)
        backup_row.addWidget(import_btn)
        backup_layout.addLayout(backup_row)

        layout.addWidget(backup_box)
        layout.addStretch()

    def _toggle_visibility(self):
        if self.key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_btn.setText("Masquer")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_btn.setText("Afficher")

    def _save(self):
        key = self.key_input.text().strip()
        config.set_api_key(key)
        QMessageBox.information(self, "Enregistré", "Clé API enregistrée localement.")

    def _export_backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter mes données", "schoolai_backup.db", "Base de données (*.db)"
        )
        if not path:
            return
        try:
            shutil.copy(db_module.DB_PATH, path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'export", str(e))
            return
        QMessageBox.information(self, "Export réussi", f"Données exportées vers :\n{path}")

    def _import_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer une sauvegarde", "", "Base de données (*.db)"
        )
        if not path:
            return
        confirm = QMessageBox.question(
            self, "Confirmer l'import",
            "Ceci va remplacer toutes tes données actuelles par celles du fichier importé. "
            "Continuer ?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.copy(path, db_module.DB_PATH)
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'import", str(e))
            return
        QMessageBox.information(
            self, "Import réussi",
            "Données importées. Redémarre l'application pour que les changements prennent effet."
        )
