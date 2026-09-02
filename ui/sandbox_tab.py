from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QTextEdit, QPushButton, QListWidget, QMessageBox, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import ai_client
from ocr_utils import extract_text_from_file

AI_WARNING = "⚠️ Contenu généré par IA — relis-le avant de t'y fier."


class _GenExerciseWorker(QThread):
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, subject, instructions, source_content):
        super().__init__()
        self.args = (subject, instructions, source_content)

    def run(self):
        try:
            result = ai_client.generate_exercises(*self.args)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class _CorrectionWorker(QThread):
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, subject, exercise_text, user_answer):
        super().__init__()
        self.args = (subject, exercise_text, user_answer)

    def run(self):
        try:
            result = ai_client.correct_exercise(*self.args)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class SandboxTab(QWidget):
    """Génère ou importe des exercices, permet à l'élève d'y répondre, puis
    demande une correction méthodique à l'IA."""

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.gen_worker = None
        self.correction_worker = None
        self._current_exercise_id = None
        self._last_attempt_id = None

        layout = QVBoxLayout(self)
        title = QLabel("Sandbox d'exercices")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.subject_combo = QComboBox()
        self._reload_subjects()
        top.addWidget(self.subject_combo)

        self.instructions_input = QLineEdit()
        self.instructions_input.setPlaceholderText(
            "Décris les exercices voulus (ex: 5 exos sur les dérivées, niveau terminale)"
        )
        top.addWidget(self.instructions_input)
        layout.addLayout(top)

        buttons_row = QHBoxLayout()
        gen_btn = QPushButton("Générer avec l'IA")
        gen_btn.clicked.connect(self._generate)
        buttons_row.addWidget(gen_btn)

        import_btn = QPushButton("Importer / scanner un fichier")
        import_btn.clicked.connect(self._import_file)
        buttons_row.addWidget(import_btn)
        layout.addLayout(buttons_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._load_exercise)
        splitter.addWidget(self.history_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        right_layout.addWidget(QLabel("Énoncé :"))
        self.exercise_view = QTextEdit()
        self.exercise_view.setReadOnly(True)
        right_layout.addWidget(self.exercise_view)

        right_layout.addWidget(QLabel("Ta réponse :"))
        self.answer_input = QTextEdit()
        right_layout.addWidget(self.answer_input)

        self.correct_btn = QPushButton("Demander une correction méthodique")
        self.correct_btn.clicked.connect(self._request_correction)
        right_layout.addWidget(self.correct_btn)

        correction_header = QHBoxLayout()
        correction_header.addWidget(QLabel("Correction :"))
        self.regenerate_correction_btn = QPushButton("🔄 Régénérer la correction")
        self.regenerate_correction_btn.setEnabled(False)
        self.regenerate_correction_btn.clicked.connect(self._request_correction)
        correction_header.addWidget(self.regenerate_correction_btn)
        right_layout.addLayout(correction_header)

        self.ai_warning_label = QLabel(AI_WARNING)
        self.ai_warning_label.setStyleSheet("color: #b45309; font-size: 11px;")
        self.ai_warning_label.setVisible(False)
        right_layout.addWidget(self.ai_warning_label)

        self.correction_view = QTextEdit()
        right_layout.addWidget(self.correction_view)

        self.save_correction_btn = QPushButton("💾 Enregistrer mes modifications de la correction")
        self.save_correction_btn.setEnabled(False)
        self.save_correction_btn.clicked.connect(self._save_correction_edits)
        right_layout.addWidget(self.save_correction_btn)

        splitter.addWidget(right)
        splitter.setSizes([220, 600])
        layout.addWidget(splitter)

        self._reload_history()

    def generate_for_context(self, subject_id, instructions):
        """Point d'entrée utilisé par d'autres onglets (ex: feedback évaluation)
        pour lancer directement une génération d'exercices sur un contexte donné."""
        idx = self.subject_combo.findData(subject_id)
        if idx >= 0:
            self.subject_combo.setCurrentIndex(idx)
        short_instructions = (
            "Exercices ciblés sur les points faibles suivants (d'après un feedback récent) : "
            + instructions[:800]
        )
        self.instructions_input.setText(short_instructions)
        self._generate()

    def _reload_subjects(self):
        self.subject_combo.clear()
        for s in self.db.list_subjects():
            self.subject_combo.addItem(s["name"], s["id"])

    def _generate(self):
        subject_id = self.subject_combo.currentData()
        instructions = self.instructions_input.text().strip()
        if subject_id is None or not instructions:
            QMessageBox.warning(self, "Champs manquants", "Sélectionne une matière et décris les exercices voulus.")
            return

        subject_name = self.subject_combo.currentText()
        self.gen_worker = _GenExerciseWorker(subject_name, instructions, "")
        self.gen_worker.finished_ok.connect(lambda text: self._save_generated(subject_id, instructions, text))
        self.gen_worker.finished_err.connect(lambda msg: QMessageBox.critical(self, "Erreur IA", msg))
        self.gen_worker.start()

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un fichier", "", "Documents (*.txt *.md *.pdf *.png *.jpg *.jpeg)"
        )
        if not path:
            return
        subject_id = self.subject_combo.currentData()
        if subject_id is None:
            QMessageBox.warning(self, "Aucune matière", "Ajoute d'abord une matière.")
            return
        try:
            content = extract_text_from_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'import", str(e))
            return

        title = f"Import - {path.split('/')[-1]}"
        self.db.add_exercise(subject_id, title, content, source="import")
        self._reload_history()
        QMessageBox.information(self, "Import réussi", "Le fichier a été importé comme exercice.")

    def _save_generated(self, subject_id, instructions, text):
        title = f"Généré - {instructions[:40]}"
        self.db.add_exercise(subject_id, title, text, source="ai")
        self.instructions_input.clear()
        self._reload_history()

    def _reload_history(self):
        self.history_list.clear()
        self._exercises = self.db.list_exercises()
        for ex in self._exercises:
            self.history_list.addItem(f"{ex['subject_name']} - {ex['title']}")

    def _load_exercise(self, item):
        idx = self.history_list.row(item)
        ex = self._exercises[idx]
        self._current_exercise_id = ex["id"]
        self._current_subject_name = ex["subject_name"]
        self.exercise_view.setMarkdown(ex["content_md"])
        self.answer_input.clear()
        self.correction_view.clear()
        self.ai_warning_label.setVisible(False)
        self.regenerate_correction_btn.setEnabled(False)
        self.save_correction_btn.setEnabled(False)
        self._last_attempt_id = None

        last_attempt = self.db.get_last_attempt(ex["id"])
        if last_attempt:
            self.answer_input.setPlainText(last_attempt["user_answer"])
            if last_attempt["ai_correction"]:
                self.correction_view.setMarkdown(last_attempt["ai_correction"])
                self.ai_warning_label.setVisible(True)
                self.regenerate_correction_btn.setEnabled(True)
                self.save_correction_btn.setEnabled(True)
                self._last_attempt_id = last_attempt["id"]

    def _request_correction(self):
        if self._current_exercise_id is None:
            QMessageBox.warning(self, "Aucun exercice", "Sélectionne d'abord un exercice.")
            return
        answer = self.answer_input.toPlainText().strip()
        if not answer:
            QMessageBox.warning(self, "Réponse vide", "Écris ta réponse avant de demander une correction.")
            return

        exercise_text = self.exercise_view.toPlainText()
        self.correct_btn.setEnabled(False)
        self.correct_btn.setText("Correction en cours...")
        self.regenerate_correction_btn.setEnabled(False)

        self.correction_worker = _CorrectionWorker(self._current_subject_name, exercise_text, answer)
        self.correction_worker.finished_ok.connect(self._on_correction_done)
        self.correction_worker.finished_err.connect(self._on_correction_error)
        self.correction_worker.start()

    def _on_correction_done(self, text):
        self.correct_btn.setEnabled(True)
        self.correct_btn.setText("Demander une correction méthodique")
        self.regenerate_correction_btn.setEnabled(True)
        self.save_correction_btn.setEnabled(True)
        self.ai_warning_label.setVisible(True)
        self.correction_view.setMarkdown(text)
        self._last_attempt_id = self.db.save_attempt(
            self._current_exercise_id, self.answer_input.toPlainText(), text
        )

    def _on_correction_error(self, message):
        self.correct_btn.setEnabled(True)
        self.correct_btn.setText("Demander une correction méthodique")
        self.regenerate_correction_btn.setEnabled(self._last_attempt_id is not None)
        QMessageBox.critical(self, "Erreur IA", message)

    def _save_correction_edits(self):
        if self._last_attempt_id is None:
            return
        self.db.update_attempt_correction(self._last_attempt_id, self.correction_view.toMarkdown())
        QMessageBox.information(self, "Enregistré", "Tes modifications de la correction ont été sauvegardées.")

    def refresh(self):
        self._reload_subjects()
        self._reload_history()
