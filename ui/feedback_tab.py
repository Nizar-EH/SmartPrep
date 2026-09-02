from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QTextEdit, QPushButton, QDoubleSpinBox, QSpinBox, QListWidget, QMessageBox,
    QSplitter, QFileDialog, QDateEdit, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate

import ai_client
from ocr_utils import extract_text_from_file

AI_WARNING = "⚠️ Contenu généré par IA — relis-le avant de t'y fier."


class _FeedbackWorker(QThread):
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, subject, title, grade, max_grade, details):
        super().__init__()
        self.args = (subject, title, grade, max_grade, details)

    def run(self):
        try:
            result = ai_client.feedback_evaluation(*self.args)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class _ScanExtractWorker(QThread):
    finished_ok = pyqtSignal(dict, str)
    finished_err = pyqtSignal(str)

    def __init__(self, raw_text):
        super().__init__()
        self.raw_text = raw_text

    def run(self):
        try:
            data = ai_client.extract_evaluation_from_scan(self.raw_text)
            self.finished_ok.emit(data, self.raw_text)
        except Exception as e:
            self.finished_err.emit(str(e))


class FeedbackTab(QWidget):
    """Enregistre une évaluation et obtient un feedback IA, gère aussi les
    évaluations à venir et permet d'importer un scan de copie/bulletin."""

    def __init__(self, db, on_generate_revision=None, on_generate_exercises=None):
        super().__init__()
        self.db = db
        self.on_generate_revision = on_generate_revision
        self.on_generate_exercises = on_generate_exercises
        self.worker = None
        self.scan_worker = None
        self._current_eval_id = None
        self._current_eval_subject_id = None

        outer_layout = QVBoxLayout(self)
        title = QLabel("Feedback sur les évaluations")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        outer_layout.addWidget(title)

        sub_tabs = QTabWidget()
        outer_layout.addWidget(sub_tabs)

        # ---------- Sous-onglet : évaluations notées + feedback ----------
        graded_widget = QWidget()
        layout = QVBoxLayout(graded_widget)

        form = QHBoxLayout()
        self.subject_combo = QComboBox()
        self._reload_subjects()
        form.addWidget(self.subject_combo)

        self.eval_title = QLineEdit()
        self.eval_title.setPlaceholderText("Nom de l'évaluation (ex: DS n°2)")
        form.addWidget(self.eval_title)

        self.grade_input = QDoubleSpinBox()
        self.grade_input.setRange(0, 100)
        self.grade_input.setDecimals(2)
        self.grade_input.setPrefix("Note: ")
        form.addWidget(self.grade_input)

        self.max_grade_input = QDoubleSpinBox()
        self.max_grade_input.setRange(1, 100)
        self.max_grade_input.setValue(20)
        self.max_grade_input.setPrefix("/ ")
        form.addWidget(self.max_grade_input)

        self.trimester_input = QSpinBox()
        self.trimester_input.setRange(1, 3)
        self.trimester_input.setPrefix("Trimestre ")
        form.addWidget(self.trimester_input)
        layout.addLayout(form)

        self.details_input = QTextEdit()
        self.details_input.setPlaceholderText(
            "Détails optionnels : ce que le prof a dit, points perdus, questions ratées..."
        )
        self.details_input.setFixedHeight(90)
        layout.addWidget(self.details_input)

        buttons_row = QHBoxLayout()
        self.submit_btn = QPushButton("Enregistrer et obtenir le feedback")
        self.submit_btn.clicked.connect(self._submit)
        buttons_row.addWidget(self.submit_btn)

        import_scan_btn = QPushButton("📷 Importer un scan de copie/bulletin")
        import_scan_btn.clicked.connect(self._import_scan)
        buttons_row.addWidget(import_scan_btn)
        layout.addLayout(buttons_row)

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
        self.regenerate_btn = QPushButton("🔄 Régénérer le feedback")
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.clicked.connect(self._regenerate)
        actions_row.addWidget(self.regenerate_btn)

        self.save_edits_btn = QPushButton("💾 Enregistrer mes modifications")
        self.save_edits_btn.setEnabled(False)
        self.save_edits_btn.clicked.connect(self._save_edits)
        actions_row.addWidget(self.save_edits_btn)
        right_layout.addLayout(actions_row)

        followup_row = QHBoxLayout()
        self.gen_revision_btn = QPushButton("📘 Générer une fiche de révision sur ce sujet")
        self.gen_revision_btn.setEnabled(False)
        self.gen_revision_btn.clicked.connect(self._trigger_generate_revision)
        followup_row.addWidget(self.gen_revision_btn)

        self.gen_exercises_btn = QPushButton("📝 Générer des exercices sur ce point")
        self.gen_exercises_btn.setEnabled(False)
        self.gen_exercises_btn.clicked.connect(self._trigger_generate_exercises)
        followup_row.addWidget(self.gen_exercises_btn)
        right_layout.addLayout(followup_row)

        splitter.addWidget(right)
        splitter.setSizes([220, 500])
        layout.addWidget(splitter)

        sub_tabs.addTab(graded_widget, "Évaluations passées")

        # ---------- Sous-onglet : évaluations à venir ----------
        upcoming_widget = QWidget()
        up_layout = QVBoxLayout(upcoming_widget)
        up_layout.addWidget(QLabel(
            "Planifie tes prochaines évaluations pour garder une vue d'ensemble sur le tableau de bord."
        ))

        up_form = QHBoxLayout()
        self.up_subject_combo = QComboBox()
        up_form.addWidget(self.up_subject_combo)

        self.up_title_input = QLineEdit()
        self.up_title_input.setPlaceholderText("Nom de l'évaluation")
        up_form.addWidget(self.up_title_input)

        self.up_date_input = QDateEdit(calendarPopup=True)
        self.up_date_input.setDate(QDate.currentDate())
        up_form.addWidget(self.up_date_input)
        up_layout.addLayout(up_form)

        self.up_notes_input = QLineEdit()
        self.up_notes_input.setPlaceholderText("Notes optionnelles (chapitres à réviser, format de l'épreuve...)")
        up_layout.addWidget(self.up_notes_input)

        up_add_btn = QPushButton("Ajouter à venir")
        up_add_btn.clicked.connect(self._add_upcoming)
        up_layout.addWidget(up_add_btn)

        self.upcoming_list = QListWidget()
        up_layout.addWidget(self.upcoming_list)

        up_delete_btn = QPushButton("Supprimer la sélection")
        up_delete_btn.clicked.connect(self._delete_upcoming)
        up_layout.addWidget(up_delete_btn)

        sub_tabs.addTab(upcoming_widget, "Évaluations à venir")

        self._reload_history()
        self._reload_upcoming()

    # ---------- évaluations notées ----------
    def _reload_subjects(self):
        self.subject_combo.clear()
        for s in self.db.list_subjects():
            self.subject_combo.addItem(s["name"], s["id"])

    def _submit(self):
        subject_id = self.subject_combo.currentData()
        title = self.eval_title.text().strip()
        if subject_id is None or not title:
            QMessageBox.warning(self, "Champs manquants", "Sélectionne une matière et un nom d'évaluation.")
            return

        subject_name = self.subject_combo.currentText()
        grade = self.grade_input.value()
        max_grade = self.max_grade_input.value()
        details = self.details_input.toPlainText().strip()

        self._pending_subject_id = subject_id
        self._pending_title = title
        self._pending_grade = grade
        self._pending_max_grade = max_grade

        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Analyse en cours...")

        self.worker = _FeedbackWorker(subject_name, title, grade, max_grade, details)
        self.worker.finished_ok.connect(self._on_submit_done)
        self.worker.finished_err.connect(self._on_error)
        self.worker.start()

    def _on_submit_done(self, feedback_text):
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Enregistrer et obtenir le feedback")
        trimester = self.trimester_input.value()
        self._current_eval_id = self.db.add_evaluation(
            self._pending_subject_id, self._pending_title, date.today().isoformat(),
            self._pending_grade, self._pending_max_grade, trimester, feedback_text
        )
        self._current_eval_subject_id = self._pending_subject_id
        self.result_view.setMarkdown(feedback_text)
        self.ai_warning_label.setVisible(True)
        self.regenerate_btn.setEnabled(True)
        self.save_edits_btn.setEnabled(True)
        self.gen_revision_btn.setEnabled(True)
        self.gen_exercises_btn.setEnabled(True)
        self.eval_title.clear()
        self.details_input.clear()
        self._reload_history()

    def _regenerate(self):
        if self._current_eval_id is None:
            return
        subject_name = self.subject_combo.currentText()
        # on relance avec les dernières valeurs affichées dans le formulaire s'il y en a,
        # sinon on réutilise l'historique via la sélection courante
        title = self.eval_title.text().strip() or "Évaluation"
        grade = self.grade_input.value()
        max_grade = self.max_grade_input.value()
        details = self.details_input.toPlainText().strip()

        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setText("Régénération...")
        self.worker = _FeedbackWorker(subject_name, title, grade, max_grade, details)
        self.worker.finished_ok.connect(self._on_regenerate_done)
        self.worker.finished_err.connect(self._on_error)
        self.worker.start()

    def _on_regenerate_done(self, feedback_text):
        self.regenerate_btn.setEnabled(True)
        self.regenerate_btn.setText("🔄 Régénérer le feedback")
        self.result_view.setMarkdown(feedback_text)
        if self._current_eval_id is not None:
            self.db.update_evaluation_feedback(self._current_eval_id, feedback_text)
        self._reload_history()

    def _on_error(self, message):
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Enregistrer et obtenir le feedback")
        self.regenerate_btn.setEnabled(self._current_eval_id is not None)
        self.regenerate_btn.setText("🔄 Régénérer le feedback")
        QMessageBox.critical(self, "Erreur IA", message)

    def _save_edits(self):
        if self._current_eval_id is None:
            return
        self.db.update_evaluation_feedback(self._current_eval_id, self.result_view.toMarkdown())
        QMessageBox.information(self, "Enregistré", "Tes modifications ont été sauvegardées.")
        self._reload_history()

    def _reload_history(self):
        self.history_list.clear()
        self._evals = self.db.list_evaluations()
        for e in self._evals:
            self.history_list.addItem(f"{e['subject_name']} - {e['title']} : {e['grade']}/{e['max_grade']}")

    def _show_history_item(self, item):
        idx = self.history_list.row(item)
        e = self._evals[idx]
        self._current_eval_id = e["id"]
        self._current_eval_subject_id = e["subject_id"]
        self.result_view.setMarkdown(e["ai_feedback"] or "_Pas de feedback enregistré._")
        self.ai_warning_label.setVisible(bool(e["ai_feedback"]))
        self.regenerate_btn.setEnabled(True)
        self.save_edits_btn.setEnabled(True)
        self.gen_revision_btn.setEnabled(True)
        self.gen_exercises_btn.setEnabled(True)

    def _trigger_generate_revision(self):
        if self._current_eval_subject_id is None or self.on_generate_revision is None:
            return
        context = self.result_view.toPlainText()
        self.on_generate_revision(self._current_eval_subject_id, context)

    def _trigger_generate_exercises(self):
        if self._current_eval_subject_id is None or self.on_generate_exercises is None:
            return
        context = self.result_view.toPlainText()
        self.on_generate_exercises(self._current_eval_subject_id, context)

    def _import_scan(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un scan", "", "Documents (*.txt *.pdf *.png *.jpg *.jpeg)"
        )
        if not path:
            return
        try:
            content = extract_text_from_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'import", str(e))
            return
        if not content.strip():
            QMessageBox.warning(self, "Rien détecté", "Aucun texte n'a pu être extrait de ce fichier.")
            return

        self.details_input.setPlainText(content)
        self.scan_worker = _ScanExtractWorker(content)
        self.scan_worker.finished_ok.connect(self._on_scan_extracted)
        self.scan_worker.finished_err.connect(
            lambda msg: QMessageBox.information(
                self, "Analyse partielle",
                "Le texte a été importé dans les détails, mais l'extraction automatique a échoué : "
                f"remplis les champs manuellement.\n({msg})"
            )
        )
        self.scan_worker.start()

    def _on_scan_extracted(self, data, raw_text):
        if data.get("title"):
            self.eval_title.setText(str(data["title"]))
        if data.get("grade") is not None:
            try:
                self.grade_input.setValue(float(data["grade"]))
            except (TypeError, ValueError):
                pass
        if data.get("max_grade") is not None:
            try:
                self.max_grade_input.setValue(float(data["max_grade"]))
            except (TypeError, ValueError):
                pass
        if data.get("subject_guess"):
            idx = self.subject_combo.findText(str(data["subject_guess"]))
            if idx >= 0:
                self.subject_combo.setCurrentIndex(idx)
        QMessageBox.information(
            self, "Scan analysé",
            "Les champs ont été pré-remplis à partir du scan quand possible. "
            "Vérifie-les avant de valider."
        )

    # ---------- évaluations à venir ----------
    def _reload_upcoming_subjects(self):
        self.up_subject_combo.clear()
        for s in self.db.list_subjects():
            self.up_subject_combo.addItem(s["name"], s["id"])

    def _reload_upcoming(self):
        self._reload_upcoming_subjects()
        self.upcoming_list.clear()
        self._upcoming = self.db.list_upcoming_evaluations()
        for u in self._upcoming:
            note = f" — {u['notes']}" if u["notes"] else ""
            self.upcoming_list.addItem(f"{u['date']} · {u['subject_name']} — {u['title']}{note}")

    def _add_upcoming(self):
        subject_id = self.up_subject_combo.currentData()
        title = self.up_title_input.text().strip()
        if subject_id is None or not title:
            QMessageBox.warning(self, "Champs manquants", "Sélectionne une matière et un nom d'évaluation.")
            return
        date_str = self.up_date_input.date().toString("yyyy-MM-dd")
        notes = self.up_notes_input.text().strip()
        self.db.add_upcoming_evaluation(subject_id, title, date_str, notes)
        self.up_title_input.clear()
        self.up_notes_input.clear()
        self._reload_upcoming()

    def _delete_upcoming(self):
        row = self.upcoming_list.currentRow()
        if row < 0:
            return
        entry = self._upcoming[row]
        self.db.delete_upcoming_evaluation(entry["id"])
        self._reload_upcoming()

    def refresh(self):
        self._reload_subjects()
        self._reload_history()
        self._reload_upcoming()
