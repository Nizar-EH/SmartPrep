from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QCheckBox, QDateEdit, QLineEdit, QTextEdit, QMessageBox, QGroupBox,
    QScrollArea
)
from PyQt6.QtCore import Qt, QDate, QTimer, QThread, pyqtSignal

import ai_client
import exam_tracks

AI_WARNING = "⚠️ Contenu généré par IA — relis-le avant de t'y fier."


class _PlanWorker(QThread):
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, track_label, remaining_items, weak_subjects, days_left):
        super().__init__()
        self.args = (track_label, remaining_items, weak_subjects, days_left)

    def run(self):
        try:
            result = ai_client.generate_exam_prep_plan(*self.args)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class ExamTab(QWidget):
    """Suivi spécial pour Brevet (3e), Bac de français (1ère), et Bac +
    Grand Oral (Terminale) : checklist d'épreuves, compte à rebours, et
    préparation dédiée au Grand Oral en Terminale."""

    def __init__(self, db, on_generate_exercises=None):
        super().__init__()
        self.db = db
        self.on_generate_exercises = on_generate_exercises
        self.plan_worker = None
        self.item_checkboxes = {}
        self.item_dates = {}

        outer = QVBoxLayout(self)
        title = QLabel("🎓 Suivi examen")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        outer.addWidget(title)

        track_row = QHBoxLayout()
        track_row.addWidget(QLabel("Parcours :"))
        self.track_combo = QComboBox()
        self.track_combo.addItem("Aucun suivi particulier", None)
        for key, label in exam_tracks.TRACKS.items():
            self.track_combo.addItem(label, key)
        self.track_combo.currentIndexChanged.connect(self._on_track_changed)
        track_row.addWidget(self.track_combo)
        track_row.addStretch()
        outer.addLayout(track_row)

        self.countdown_label = QLabel()
        self.countdown_label.setStyleSheet("font-size: 13px; color: #2563eb; font-weight: bold;")
        outer.addWidget(self.countdown_label)

        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("color: #555; font-size: 11px;")
        outer.addWidget(self.notes_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        scroll.setWidget(self.content_widget)
        outer.addWidget(scroll)

        self.checklist_box = QGroupBox("Épreuves")
        self.checklist_layout = QVBoxLayout(self.checklist_box)
        self.content_layout.addWidget(self.checklist_box)

        plan_row = QHBoxLayout()
        self.plan_btn = QPushButton("🧭 Obtenir un plan de révision personnalisé")
        self.plan_btn.clicked.connect(self._generate_plan)
        plan_row.addWidget(self.plan_btn)
        self.content_layout.addLayout(plan_row)

        self.plan_warning = QLabel(AI_WARNING)
        self.plan_warning.setStyleSheet("color: #b45309; font-size: 11px;")
        self.plan_warning.setVisible(False)
        self.content_layout.addWidget(self.plan_warning)

        self.plan_view = QTextEdit()
        self.plan_view.setReadOnly(True)
        self.plan_view.setFixedHeight(180)
        self.content_layout.addWidget(self.plan_view)

        # ---------- Grand Oral (Terminale uniquement) ----------
        self.grand_oral_box = QGroupBox("🎤 Préparation du Grand Oral")
        go_layout = QVBoxLayout(self.grand_oral_box)

        go_form1 = QHBoxLayout()
        go_form1.addWidget(QLabel("Sujet 1 (spécialité) :"))
        self.go_subject1 = QLineEdit()
        go_form1.addWidget(self.go_subject1)
        go_layout.addLayout(go_form1)

        self.go_question1 = QLineEdit()
        self.go_question1.setPlaceholderText("Question choisie pour le sujet 1")
        go_layout.addWidget(self.go_question1)

        go_form2 = QHBoxLayout()
        go_form2.addWidget(QLabel("Sujet 2 (spécialité) :"))
        self.go_subject2 = QLineEdit()
        go_form2.addWidget(self.go_subject2)
        go_layout.addLayout(go_form2)

        self.go_question2 = QLineEdit()
        self.go_question2.setPlaceholderText("Question choisie pour le sujet 2")
        go_layout.addWidget(self.go_question2)

        self.go_notes = QTextEdit()
        self.go_notes.setPlaceholderText("Notes de préparation, arguments clés, plan de l'exposé...")
        self.go_notes.setFixedHeight(80)
        go_layout.addWidget(self.go_notes)

        go_buttons = QHBoxLayout()
        save_go_btn = QPushButton("💾 Enregistrer")
        save_go_btn.clicked.connect(self._save_grand_oral)
        go_buttons.addWidget(save_go_btn)

        gen_questions_btn = QPushButton("📝 Générer des questions d'entraînement")
        gen_questions_btn.clicked.connect(self._generate_practice_questions)
        go_buttons.addWidget(gen_questions_btn)
        go_layout.addLayout(go_buttons)

        timer_row = QHBoxLayout()
        self.timer_label = QLabel("05:00")
        self.timer_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        timer_row.addWidget(self.timer_label)

        start_expose_btn = QPushButton("▶️ Chrono exposé (5 min)")
        start_expose_btn.clicked.connect(lambda: self._start_timer(5 * 60))
        timer_row.addWidget(start_expose_btn)

        start_entretien_btn = QPushButton("▶️ Chrono entretien (20 min)")
        start_entretien_btn.clicked.connect(lambda: self._start_timer(20 * 60))
        timer_row.addWidget(start_entretien_btn)

        stop_btn = QPushButton("⏹ Arrêter")
        stop_btn.clicked.connect(self._stop_timer)
        timer_row.addWidget(stop_btn)
        go_layout.addLayout(timer_row)

        self.content_layout.addWidget(self.grand_oral_box)

        self._qtimer = QTimer()
        self._qtimer.timeout.connect(self._tick_timer)
        self._remaining_seconds = 0

        self.refresh()

    # ---------- sélection du parcours ----------
    def _on_track_changed(self):
        track = self.track_combo.currentData()
        self.db.set_exam_track(track)
        self._rebuild()

    def _rebuild(self):
        track = self.track_combo.currentData()

        # nettoyer la checklist actuelle
        while self.checklist_layout.count():
            item = self.checklist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.item_checkboxes = {}
        self.item_dates = {}

        if track is None:
            self.countdown_label.setText("")
            self.notes_label.setText("")
            self.checklist_box.setVisible(False)
            self.plan_btn.setVisible(False)
            self.plan_view.setVisible(False)
            self.plan_warning.setVisible(False)
            self.grand_oral_box.setVisible(False)
            return

        self.checklist_box.setVisible(True)
        self.plan_btn.setVisible(True)
        self.notes_label.setText(exam_tracks.NOTES.get(track, ""))

        progress = self.db.get_exam_progress(track)
        for item_key, label, default_date, coef in exam_tracks.CHECKLISTS[track]:
            row = QHBoxLayout()
            saved = progress.get(item_key)

            checkbox = QCheckBox(f"{label} — {coef}")
            checkbox.setChecked(bool(saved and saved["done"]))
            checkbox.stateChanged.connect(
                lambda state, k=item_key: self._on_item_toggled(k, state)
            )
            row.addWidget(checkbox)
            self.item_checkboxes[item_key] = checkbox

            date_str = (saved and saved.get("custom_date")) or default_date
            date_edit = QDateEdit(calendarPopup=True)
            if date_str:
                date_edit.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
            else:
                date_edit.setDate(QDate.currentDate())
            date_edit.dateChanged.connect(
                lambda d, k=item_key: self._on_item_date_changed(k, d)
            )
            row.addWidget(date_edit)
            self.item_dates[item_key] = date_edit

            row_widget = QWidget()
            row_widget.setLayout(row)
            self.checklist_layout.addWidget(row_widget)

        self._update_countdown(track)

        is_terminale = track == "bac_terminale"
        self.grand_oral_box.setVisible(is_terminale)
        if is_terminale:
            self._load_grand_oral()

    def _on_item_toggled(self, item_key, state):
        track = self.track_combo.currentData()
        self.db.set_exam_item(track, item_key, done=bool(state))
        self._update_countdown(track)

    def _on_item_date_changed(self, item_key, qdate):
        track = self.track_combo.currentData()
        self.db.set_exam_item(track, item_key, custom_date=qdate.toString("yyyy-MM-dd"))
        self._update_countdown(track)

    def _update_countdown(self, track):
        progress = self.db.get_exam_progress(track)
        upcoming_dates = []
        for item_key, label, default_date, coef in exam_tracks.CHECKLISTS[track]:
            if progress.get(item_key, {}).get("done"):
                continue
            date_str = (progress.get(item_key) or {}).get("custom_date") or default_date
            if date_str:
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if d >= date.today():
                        upcoming_dates.append((d, label))
                except ValueError:
                    pass

        if upcoming_dates:
            upcoming_dates.sort()
            next_date, next_label = upcoming_dates[0]
            days_left = (next_date - date.today()).days
            self.countdown_label.setText(f"⏳ {days_left} jour(s) avant : {next_label} ({next_date.strftime('%d/%m/%Y')})")
        else:
            self.countdown_label.setText("Pas d'échéance à venir (dates non renseignées ou tout est coché).")

    # ---------- plan de révision IA ----------
    def _generate_plan(self):
        track = self.track_combo.currentData()
        if track is None:
            return
        track_label = exam_tracks.TRACKS[track]
        progress = self.db.get_exam_progress(track)
        remaining = [
            (k, label, coef) for k, label, _, coef in exam_tracks.CHECKLISTS[track]
            if not progress.get(k, {}).get("done")
        ]
        averages = self.db.subject_averages()
        weak_subjects = [a["subject_name"] for a in averages[:3]]

        upcoming_dates = []
        for item_key, label, default_date, coef in exam_tracks.CHECKLISTS[track]:
            date_str = (progress.get(item_key) or {}).get("custom_date") or default_date
            if date_str:
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if d >= date.today():
                        upcoming_dates.append(d)
                except ValueError:
                    pass
        days_left = (min(upcoming_dates) - date.today()).days if upcoming_dates else None

        self.plan_btn.setEnabled(False)
        self.plan_btn.setText("Génération en cours...")
        self.plan_worker = _PlanWorker(track_label, remaining, weak_subjects, days_left)
        self.plan_worker.finished_ok.connect(self._on_plan_done)
        self.plan_worker.finished_err.connect(self._on_plan_error)
        self.plan_worker.start()

    def _on_plan_done(self, text):
        self.plan_btn.setEnabled(True)
        self.plan_btn.setText("🧭 Obtenir un plan de révision personnalisé")
        self.plan_view.setVisible(True)
        self.plan_view.setMarkdown(text)
        self.plan_warning.setVisible(True)

    def _on_plan_error(self, message):
        self.plan_btn.setEnabled(True)
        self.plan_btn.setText("🧭 Obtenir un plan de révision personnalisé")
        QMessageBox.critical(self, "Erreur IA", message)

    # ---------- Grand Oral ----------
    def _load_grand_oral(self):
        prep = self.db.get_grand_oral_prep()
        if prep:
            self.go_subject1.setText(prep.get("subject1") or "")
            self.go_question1.setText(prep.get("question1") or "")
            self.go_subject2.setText(prep.get("subject2") or "")
            self.go_question2.setText(prep.get("question2") or "")
            self.go_notes.setPlainText(prep.get("notes") or "")

    def _save_grand_oral(self):
        self.db.save_grand_oral_prep(
            self.go_subject1.text().strip(),
            self.go_question1.text().strip(),
            self.go_subject2.text().strip(),
            self.go_question2.text().strip(),
            self.go_notes.toPlainText().strip(),
        )
        QMessageBox.information(self, "Enregistré", "Ta préparation du Grand Oral a été sauvegardée.")

    def _generate_practice_questions(self):
        if self.on_generate_exercises is None:
            return
        subject_text = self.go_subject1.text().strip() or self.go_subject2.text().strip()
        if not subject_text:
            QMessageBox.warning(self, "Sujet manquant", "Renseigne au moins un sujet de spécialité.")
            return
        subjects = self.db.list_subjects()
        match = next((s for s in subjects if s["name"].lower() in subject_text.lower()
                      or subject_text.lower() in s["name"].lower()), None)
        subject_id = match["id"] if match else (subjects[0]["id"] if subjects else None)
        if subject_id is None:
            QMessageBox.warning(self, "Aucune matière", "Ajoute d'abord une matière.")
            return
        instructions = (
            f"5 questions possibles de Grand Oral, dans l'esprit du jury, sur le sujet : "
            f"{self.go_subject1.text()} — {self.go_question1.text()} "
            f"/ {self.go_subject2.text()} — {self.go_question2.text()}"
        )
        self.on_generate_exercises(subject_id, instructions)

    # ---------- chrono ----------
    def _start_timer(self, seconds):
        self._remaining_seconds = seconds
        self._update_timer_label()
        self._qtimer.start(1000)

    def _stop_timer(self):
        self._qtimer.stop()

    def _tick_timer(self):
        self._remaining_seconds -= 1
        if self._remaining_seconds <= 0:
            self._qtimer.stop()
            self._remaining_seconds = 0
            QMessageBox.information(self, "Temps écoulé", "Le temps est écoulé !")
        self._update_timer_label()

    def _update_timer_label(self):
        m, s = divmod(max(self._remaining_seconds, 0), 60)
        self.timer_label.setText(f"{m:02d}:{s:02d}")

    def refresh(self):
        saved_track = self.db.get_exam_track()
        if saved_track is None:
            profile = self.db.get_profile()
            detected = exam_tracks.detect_track_from_classe(profile["classe"]) if profile else None
            if detected:
                saved_track = detected
                self.db.set_exam_track(detected)

        idx = self.track_combo.findData(saved_track)
        if idx >= 0 and idx != self.track_combo.currentIndex():
            self.track_combo.blockSignals(True)
            self.track_combo.setCurrentIndex(idx)
            self.track_combo.blockSignals(False)
        self._rebuild()
