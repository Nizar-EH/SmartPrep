from datetime import date, datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QGroupBox

import exam_tracks


class DashboardTab(QWidget):
    """Vue d'ensemble affichée en premier : évaluations à venir, matières à
    renforcer d'après les moyennes, et activité récente."""

    def __init__(self, db):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)
        self.greeting_label = QLabel()
        self.greeting_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.greeting_label)

        self.exam_countdown_label = QLabel()
        self.exam_countdown_label.setStyleSheet("font-size: 13px; color: #2563eb; font-weight: bold;")
        layout.addWidget(self.exam_countdown_label)

        row = QHBoxLayout()

        upcoming_box = QGroupBox("📅 Évaluations à venir")
        upcoming_layout = QVBoxLayout(upcoming_box)
        self.upcoming_list = QListWidget()
        upcoming_layout.addWidget(self.upcoming_list)
        row.addWidget(upcoming_box)

        weak_box = QGroupBox("📉 Matières à renforcer")
        weak_layout = QVBoxLayout(weak_box)
        self.weak_list = QListWidget()
        weak_layout.addWidget(self.weak_list)
        row.addWidget(weak_box)

        layout.addLayout(row)

        activity_box = QGroupBox("🕓 Activité récente")
        activity_layout = QVBoxLayout(activity_box)
        self.activity_list = QListWidget()
        activity_layout.addWidget(self.activity_list)
        layout.addWidget(activity_box)

        self.refresh()

    def refresh(self):
        profile = self.db.get_profile()
        if profile:
            self.greeting_label.setText(f"Bonjour {profile['nom']} 👋  ({profile['classe']})")

        self._update_exam_countdown()

        # évaluations à venir
        self.upcoming_list.clear()
        upcoming = self.db.list_upcoming_evaluations(limit=8)
        if not upcoming:
            self.upcoming_list.addItem("Aucune évaluation à venir planifiée.")
        for u in upcoming:
            self.upcoming_list.addItem(f"{u['date']} · {u['subject_name']} — {u['title']}")

        # matières à renforcer (3 plus faibles moyennes)
        self.weak_list.clear()
        averages = self.db.subject_averages()
        if not averages:
            self.weak_list.addItem("Pas encore assez d'évaluations notées.")
        for a in averages[:3]:
            self.weak_list.addItem(f"{a['subject_name']} — moyenne {a['average']:.1f}/20")

        # activité récente : fiches + entrées d'emploi du temps, fusionnées et triées
        self.activity_list.clear()
        sheets = self.db.list_revision_sheets(limit=5)
        recent_schedule = self.db.get_recent_schedule_entries(limit=5)

        items = []
        for s in sheets:
            items.append((s["created_at"], f"📘 Fiche de révision créée — {s['subject_name']} ({s['title']})"))
        for e in recent_schedule:
            items.append((e["created_at"], f"🗓️ Cours ajouté — {e['subject_name']} le {e['date']}"))

        items.sort(key=lambda x: x[0], reverse=True)
        if not items:
            self.activity_list.addItem("Aucune activité récente.")
        for _, label in items[:8]:
            self.activity_list.addItem(label)

    def _update_exam_countdown(self):
        track = self.db.get_exam_track()
        if not track:
            self.exam_countdown_label.setText("")
            return

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

        track_label = exam_tracks.TRACKS.get(track, "")
        if upcoming_dates:
            upcoming_dates.sort()
            next_date, next_label = upcoming_dates[0]
            days_left = (next_date - date.today()).days
            self.exam_countdown_label.setText(
                f"🎓 {track_label} — {days_left} jour(s) avant : {next_label}"
            )
        else:
            self.exam_countdown_label.setText(f"🎓 {track_label} — suivi actif (voir l'onglet Suivi examen)")
