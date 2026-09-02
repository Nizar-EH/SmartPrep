"""
Gestion de la base de données locale (SQLite).
Toutes les données restent sur la machine de l'utilisateur.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path.home() / ".schoolai"
APP_DIR.mkdir(exist_ok=True)
DB_PATH = APP_DIR / "schoolai.db"


class Database:
    def __init__(self, path=DB_PATH):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nom TEXT NOT NULL,
            classe TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_spe INTEGER NOT NULL DEFAULT 0
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS schedule_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            subject_id INTEGER NOT NULL,
            content_text TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )""")

        # Modèle hebdomadaire (emploi du temps type) : weekday 0=Lundi ... 6=Dimanche
        c.execute("""
        CREATE TABLE IF NOT EXISTS schedule_template (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS revision_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_md TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            grade REAL NOT NULL,
            max_grade REAL NOT NULL DEFAULT 20,
            trimester INTEGER NOT NULL,
            ai_feedback TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )""")

        # Évaluations à venir (pas encore passées / pas encore notées)
        c.execute("""
        CREATE TABLE IF NOT EXISTS upcoming_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_md TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'ai',
            created_at TEXT NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS exercise_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            user_answer TEXT NOT NULL,
            ai_correction TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS exam_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            track TEXT
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS exam_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track TEXT NOT NULL,
            item_key TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            custom_date TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(track, item_key)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS grand_oral_prep (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            subject1 TEXT,
            question1 TEXT,
            subject2 TEXT,
            question2 TEXT,
            notes TEXT,
            updated_at TEXT
        )""")

        self.conn.commit()
    def get_profile(self):
        row = self.conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        return dict(row) if row else None

    def save_profile(self, nom, classe):
        self.conn.execute(
            "INSERT INTO profile (id, nom, classe, created_at) VALUES (1, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET nom=excluded.nom, classe=excluded.classe",
            (nom, classe, datetime.now().isoformat())
        )
        self.conn.commit()

    # ---------- subjects ----------
    def add_subject(self, name, is_spe=False):
        self.conn.execute(
            "INSERT OR IGNORE INTO subjects (name, is_spe) VALUES (?, ?)",
            (name, int(is_spe))
        )
        self.conn.commit()

    def list_subjects(self):
        rows = self.conn.execute("SELECT * FROM subjects ORDER BY is_spe DESC, name").fetchall()
        return [dict(r) for r in rows]

    # ---------- schedule ----------
    def add_schedule_entry(self, date, start_time, subject_id, content_text, end_time=None):
        self.conn.execute(
            "INSERT INTO schedule_entries (date, start_time, end_time, subject_id, content_text, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (date, start_time, end_time, subject_id, content_text, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_schedule_for_date(self, date):
        rows = self.conn.execute(
            "SELECT se.*, s.name as subject_name FROM schedule_entries se "
            "JOIN subjects s ON s.id = se.subject_id "
            "WHERE se.date = ? ORDER BY se.start_time", (date,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_schedule_for_subject(self, subject_id, limit=50):
        rows = self.conn.execute(
            "SELECT * FROM schedule_entries WHERE subject_id = ? "
            "ORDER BY date DESC, start_time DESC LIMIT ?", (subject_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_schedule_for_range(self, date_start, date_end):
        rows = self.conn.execute(
            "SELECT se.*, s.name as subject_name FROM schedule_entries se "
            "JOIN subjects s ON s.id = se.subject_id "
            "WHERE se.date >= ? AND se.date <= ? ORDER BY se.date, se.start_time",
            (date_start, date_end)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_schedule_entries(self, limit=5):
        rows = self.conn.execute(
            "SELECT se.*, s.name as subject_name FROM schedule_entries se "
            "JOIN subjects s ON s.id = se.subject_id "
            "ORDER BY se.created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- schedule template (emploi du temps type) ----------
    def add_template_entry(self, weekday, start_time, subject_id):
        cur = self.conn.execute(
            "INSERT INTO schedule_template (weekday, start_time, subject_id) VALUES (?, ?, ?)",
            (weekday, start_time, subject_id)
        )
        self.conn.commit()
        return cur.lastrowid

    def list_template_entries(self, weekday=None):
        if weekday is not None:
            rows = self.conn.execute(
                "SELECT t.*, s.name as subject_name FROM schedule_template t "
                "JOIN subjects s ON s.id = t.subject_id WHERE t.weekday = ? "
                "ORDER BY t.start_time", (weekday,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT t.*, s.name as subject_name FROM schedule_template t "
                "JOIN subjects s ON s.id = t.subject_id ORDER BY t.weekday, t.start_time"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_template_entry(self, entry_id):
        self.conn.execute("DELETE FROM schedule_template WHERE id = ?", (entry_id,))
        self.conn.commit()

    def apply_template_to_date(self, date_str, weekday):
        """Crée une entrée d'emploi du temps (contenu vide) pour chaque ligne du
        modèle de ce jour de la semaine, en évitant les doublons (même heure +
        même matière déjà présents ce jour-là)."""
        existing = self.get_schedule_for_date(date_str)
        existing_keys = {(e["start_time"], e["subject_id"]) for e in existing}
        created = 0
        for t in self.list_template_entries(weekday):
            key = (t["start_time"], t["subject_id"])
            if key not in existing_keys:
                self.add_schedule_entry(date_str, t["start_time"], t["subject_id"], "")
                created += 1
        return created

    def duplicate_day_structure(self, source_date_str, target_date_str):
        """Copie la structure (heure + matière, contenu vide) d'un jour vers un autre."""
        existing = self.get_schedule_for_date(target_date_str)
        existing_keys = {(e["start_time"], e["subject_id"]) for e in existing}
        created = 0
        for e in self.get_schedule_for_date(source_date_str):
            key = (e["start_time"], e["subject_id"])
            if key not in existing_keys:
                self.add_schedule_entry(target_date_str, e["start_time"], e["subject_id"], "")
                created += 1
        return created

    # ---------- revision sheets ----------
    def save_revision_sheet(self, subject_id, title, content_md):
        cur = self.conn.execute(
            "INSERT INTO revision_sheets (subject_id, title, content_md, created_at) VALUES (?, ?, ?, ?)",
            (subject_id, title, content_md, datetime.now().isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def update_revision_sheet(self, sheet_id, content_md):
        self.conn.execute(
            "UPDATE revision_sheets SET content_md = ? WHERE id = ?", (content_md, sheet_id)
        )
        self.conn.commit()

    def list_revision_sheets(self, subject_id=None, limit=None):
        query = (
            "SELECT rs.*, s.name as subject_name FROM revision_sheets rs "
            "JOIN subjects s ON s.id = rs.subject_id "
        )
        params = []
        if subject_id:
            query += "WHERE rs.subject_id = ? "
            params.append(subject_id)
        query += "ORDER BY rs.created_at DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ---------- evaluations (passées, notées) ----------
    def add_evaluation(self, subject_id, title, date, grade, max_grade, trimester, ai_feedback=None):
        cur = self.conn.execute(
            "INSERT INTO evaluations (subject_id, title, date, grade, max_grade, trimester, ai_feedback, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (subject_id, title, date, grade, max_grade, trimester, ai_feedback, datetime.now().isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def update_evaluation_feedback(self, evaluation_id, ai_feedback):
        self.conn.execute(
            "UPDATE evaluations SET ai_feedback = ? WHERE id = ?", (ai_feedback, evaluation_id)
        )
        self.conn.commit()

    def list_evaluations(self, trimester=None):
        if trimester:
            rows = self.conn.execute(
                "SELECT e.*, s.name as subject_name FROM evaluations e "
                "JOIN subjects s ON s.id = e.subject_id WHERE trimester = ? "
                "ORDER BY date", (trimester,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT e.*, s.name as subject_name FROM evaluations e "
                "JOIN subjects s ON s.id = e.subject_id ORDER BY date"
            ).fetchall()
        return [dict(r) for r in rows]

    def subject_averages(self):
        """Moyenne (/20) par matière, à partir des évaluations notées."""
        rows = self.conn.execute(
            "SELECT s.id as subject_id, s.name as subject_name, "
            "AVG(e.grade * 20.0 / e.max_grade) as average "
            "FROM evaluations e JOIN subjects s ON s.id = e.subject_id "
            "GROUP BY s.id ORDER BY average ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- évaluations à venir ----------
    def add_upcoming_evaluation(self, subject_id, title, date, notes=""):
        cur = self.conn.execute(
            "INSERT INTO upcoming_evaluations (subject_id, title, date, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (subject_id, title, date, notes, datetime.now().isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def list_upcoming_evaluations(self, only_future=True, limit=None):
        query = (
            "SELECT u.*, s.name as subject_name FROM upcoming_evaluations u "
            "JOIN subjects s ON s.id = u.subject_id "
        )
        params = []
        if only_future:
            query += "WHERE u.date >= ? "
            params.append(datetime.now().date().isoformat())
        query += "ORDER BY u.date ASC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def delete_upcoming_evaluation(self, upcoming_id):
        self.conn.execute("DELETE FROM upcoming_evaluations WHERE id = ?", (upcoming_id,))
        self.conn.commit()

    # ---------- exercises (sandbox) ----------
    def add_exercise(self, subject_id, title, content_md, source="ai"):
        cur = self.conn.execute(
            "INSERT INTO exercises (subject_id, title, content_md, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (subject_id, title, content_md, source, datetime.now().isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def list_exercises(self, subject_id=None):
        if subject_id:
            rows = self.conn.execute(
                "SELECT ex.*, s.name as subject_name FROM exercises ex "
                "JOIN subjects s ON s.id = ex.subject_id WHERE ex.subject_id = ? "
                "ORDER BY ex.created_at DESC", (subject_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT ex.*, s.name as subject_name FROM exercises ex "
                "JOIN subjects s ON s.id = ex.subject_id ORDER BY ex.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def save_attempt(self, exercise_id, user_answer, ai_correction):
        cur = self.conn.execute(
            "INSERT INTO exercise_attempts (exercise_id, user_answer, ai_correction, created_at) VALUES (?, ?, ?, ?)",
            (exercise_id, user_answer, ai_correction, datetime.now().isoformat())
        )
        self.conn.commit()
        return cur.lastrowid

    def update_attempt_correction(self, attempt_id, ai_correction):
        self.conn.execute(
            "UPDATE exercise_attempts SET ai_correction = ? WHERE id = ?", (ai_correction, attempt_id)
        )
        self.conn.commit()

    def get_last_attempt(self, exercise_id):
        row = self.conn.execute(
            "SELECT * FROM exercise_attempts WHERE exercise_id = ? ORDER BY created_at DESC LIMIT 1",
            (exercise_id,)
        ).fetchone()
        return dict(row) if row else None

    # ---------- suivi d'examen ----------
    def get_exam_track(self):
        row = self.conn.execute("SELECT track FROM exam_settings WHERE id = 1").fetchone()
        return row["track"] if row else None

    def set_exam_track(self, track):
        self.conn.execute(
            "INSERT INTO exam_settings (id, track) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET track = excluded.track",
            (track,)
        )
        self.conn.commit()

    def get_exam_progress(self, track):
        rows = self.conn.execute(
            "SELECT * FROM exam_progress WHERE track = ?", (track,)
        ).fetchall()
        return {r["item_key"]: dict(r) for r in rows}

    def set_exam_item(self, track, item_key, done=None, custom_date=None, notes=None):
        existing = self.conn.execute(
            "SELECT * FROM exam_progress WHERE track = ? AND item_key = ?", (track, item_key)
        ).fetchone()
        if existing:
            new_done = existing["done"] if done is None else int(done)
            new_date = existing["custom_date"] if custom_date is None else custom_date
            new_notes = existing["notes"] if notes is None else notes
            self.conn.execute(
                "UPDATE exam_progress SET done=?, custom_date=?, notes=?, updated_at=? "
                "WHERE track=? AND item_key=?",
                (new_done, new_date, new_notes, datetime.now().isoformat(), track, item_key)
            )
        else:
            self.conn.execute(
                "INSERT INTO exam_progress (track, item_key, done, custom_date, notes, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (track, item_key, int(done or 0), custom_date, notes, datetime.now().isoformat())
            )
        self.conn.commit()

    def get_grand_oral_prep(self):
        row = self.conn.execute("SELECT * FROM grand_oral_prep WHERE id = 1").fetchone()
        return dict(row) if row else None

    def save_grand_oral_prep(self, subject1, question1, subject2, question2, notes):
        self.conn.execute(
            "INSERT INTO grand_oral_prep (id, subject1, question1, subject2, question2, notes, updated_at) "
            "VALUES (1, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET subject1=excluded.subject1, question1=excluded.question1, "
            "subject2=excluded.subject2, question2=excluded.question2, notes=excluded.notes, "
            "updated_at=excluded.updated_at",
            (subject1, question1, subject2, question2, notes, datetime.now().isoformat())
        )
        self.conn.commit()
