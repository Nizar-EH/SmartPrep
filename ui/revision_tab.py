from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit,
    QPushButton, QListWidget, QMessageBox, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrinter

import ai_client

AI_WARNING = "⚠️ Contenu généré par IA — relis-le avant de t'y fier."


class _GenerateWorker(QThread):
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, subject_name, course_content):
        super().__init__()
        self.subject_name = subject_name
        self.course_content = course_content

    def run(self):
        try:
            result = ai_client.generate_revision_sheet(self.subject_name, self.course_content)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class RevisionTab(QWidget):
    """Génère des fiches de révision à partir du contenu des cours saisis
    dans l'emploi du temps (ou d'un texte collé manuellement)."""

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.worker = None
        self._current_sheet_id = None

        layout = QVBoxLayout(self)
        title = QLabel("Fiches de révision")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.subject_combo = QComboBox()
        self._reload_subjects()
        top.addWidget(QLabel("Matière :"))
        top.addWidget(self.subject_combo)

        use_schedule_btn = QPushButton("Charger le contenu des derniers cours")
        use_schedule_btn.clicked.connect(self._load_from_schedule)
        top.addWidget(use_schedule_btn)
        layout.addLayout(top)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText(
            "Contenu du cours (ou clique sur 'Charger le contenu des derniers cours')"
        )
        layout.addWidget(self.content_input)

        gen_row = QHBoxLayout()
        self.generate_btn = QPushButton("Générer la fiche de révision")
        self.generate_btn.clicked.connect(self._generate)
        gen_row.addWidget(self.generate_btn)

        self.regenerate_btn = QPushButton("🔄 Régénérer (nouvelle version)")
        self.regenerate_btn.clicked.connect(self._generate)
        gen_row.addWidget(self.regenerate_btn)
        layout.addLayout(gen_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._show_history_item)
        splitter.addWidget(self.history_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.ai_warning_label = QLabel(AI_WARNING)
        self.ai_warning_label.setStyleSheet("color: #b45309; font-size: 11px;")
        self.ai_warning_label.setVisible(False)
        right_layout.addWidget(self.ai_warning_label)

        self.result_view = QTextEdit()
        right_layout.addWidget(self.result_view)

        actions_row = QHBoxLayout()
        self.save_edits_btn = QPushButton("💾 Enregistrer mes modifications")
        self.save_edits_btn.setEnabled(False)
        self.save_edits_btn.clicked.connect(self._save_edits)
        actions_row.addWidget(self.save_edits_btn)

        self.export_pdf_btn = QPushButton("📄 Exporter en PDF")
        self.export_pdf_btn.setEnabled(False)
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        actions_row.addWidget(self.export_pdf_btn)
        right_layout.addLayout(actions_row)

        splitter.addWidget(right)
        splitter.setSizes([200, 500])

        layout.addWidget(splitter)
        self._reload_history()

    def _reload_subjects(self):
        self.subject_combo.clear()
        for s in self.db.list_subjects():
            self.subject_combo.addItem(s["name"], s["id"])

    def _load_from_schedule(self):
        subject_id = self.subject_combo.currentData()
        if subject_id is None:
            return
        entries = self.db.get_schedule_for_subject(subject_id)
        if not entries:
            QMessageBox.information(self, "Aucune donnée",
                                     "Aucun contenu de cours enregistré pour cette matière pour le moment.")
            return
        text = "\n".join(f"[{e['date']} {e['start_time']}] {e['content_text']}" for e in reversed(entries))
        self.content_input.setPlainText(text)

    def generate_for_context(self, subject_id, course_content):
        """Point d'entrée utilisé par d'autres onglets (ex: feedback évaluation)
        pour lancer directement une génération sur un contexte donné."""
        idx = self.subject_combo.findData(subject_id)
        if idx >= 0:
            self.subject_combo.setCurrentIndex(idx)
        self.content_input.setPlainText(course_content)
        self._generate()

    def _generate(self):
        subject_id = self.subject_combo.currentData()
        content = self.content_input.toPlainText().strip()
        if subject_id is None or not content:
            QMessageBox.warning(self, "Champs manquants", "Sélectionne une matière et fournis du contenu de cours.")
            return

        subject_name = self.subject_combo.currentText()
        self.generate_btn.setEnabled(False)
        self.regenerate_btn.setEnabled(False)
        self.generate_btn.setText("Génération en cours...")
        self.result_view.setPlainText("")

        self.worker = _GenerateWorker(subject_name, content)
        self.worker.finished_ok.connect(lambda text: self._on_done(subject_id, subject_name, text))
        self.worker.finished_err.connect(self._on_error)
        self.worker.start()

    def _on_done(self, subject_id, subject_name, text):
        self.generate_btn.setEnabled(True)
        self.regenerate_btn.setEnabled(True)
        self.generate_btn.setText("Générer la fiche de révision")
        self.result_view.setMarkdown(text)
        self.ai_warning_label.setVisible(True)
        self.save_edits_btn.setEnabled(True)
        self.export_pdf_btn.setEnabled(True)
        title = f"Fiche - {subject_name}"
        self._current_sheet_id = self.db.save_revision_sheet(subject_id, title, text)
        self._reload_history()

    def _on_error(self, message):
        self.generate_btn.setEnabled(True)
        self.regenerate_btn.setEnabled(True)
        self.generate_btn.setText("Générer la fiche de révision")
        QMessageBox.critical(self, "Erreur IA", message)

    def _reload_history(self):
        self.history_list.clear()
        self._sheets = self.db.list_revision_sheets()
        for sheet in self._sheets:
            self.history_list.addItem(f"{sheet['subject_name']} - {sheet['title']} ({sheet['created_at'][:10]})")

    def _show_history_item(self, item):
        idx = self.history_list.row(item)
        sheet = self._sheets[idx]
        self._current_sheet_id = sheet["id"]
        self.result_view.setMarkdown(sheet["content_md"])
        self.ai_warning_label.setVisible(True)
        self.save_edits_btn.setEnabled(True)
        self.export_pdf_btn.setEnabled(True)

    def _save_edits(self):
        if self._current_sheet_id is None:
            return
        self.db.update_revision_sheet(self._current_sheet_id, self.result_view.toMarkdown())
        QMessageBox.information(self, "Enregistré", "Tes modifications ont été sauvegardées.")
        self._reload_history()

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exporter en PDF", "fiche_revision.pdf", "PDF (*.pdf)")
        if not path:
            return
        doc = QTextDocument()
        doc.setMarkdown(self.result_view.toMarkdown())
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        doc.print(printer)
        QMessageBox.information(self, "Export réussi", f"Fiche exportée vers :\n{path}")

    def refresh(self):
        self._reload_subjects()
        self._reload_history()
