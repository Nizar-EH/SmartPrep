from PyQt6.QtWidgets import QMainWindow, QTabWidget

from ui.dashboard_tab import DashboardTab
from ui.schedule_tab import ScheduleTab
from ui.revision_tab import RevisionTab
from ui.feedback_tab import FeedbackTab
from ui.sandbox_tab import SandboxTab
from ui.exam_tab import ExamTab
from ui.stats_tab import StatsTab
from ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        profile = db.get_profile()

        self.setWindowTitle(f"SchoolAI - {profile['nom']} ({profile['classe']})")
        self.resize(1150, 780)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab = DashboardTab(db)
        self.schedule_tab = ScheduleTab(db)
        self.revision_tab = RevisionTab(db)
        self.sandbox_tab = SandboxTab(db)
        # le feedback tab peut déclencher une génération dans les onglets révision/sandbox
        self.feedback_tab = FeedbackTab(
            db,
            on_generate_revision=self._go_generate_revision,
            on_generate_exercises=self._go_generate_exercises,
        )
        self.stats_tab = StatsTab(db)
        self.settings_tab = SettingsTab()
        self.exam_tab = ExamTab(db, on_generate_exercises=self._go_generate_exercises)

        self.tabs.addTab(self.dashboard_tab, "🏠 Accueil")
        self.tabs.addTab(self.schedule_tab, "Emploi du temps")
        self.tabs.addTab(self.revision_tab, "Fiches de révision")
        self.tabs.addTab(self.feedback_tab, "Feedback évaluations")
        self.tabs.addTab(self.sandbox_tab, "Sandbox exercices")
        self.tabs.addTab(self.exam_tab, "🎓 Suivi examen")
        self.tabs.addTab(self.stats_tab, "Statistiques")
        self.tabs.addTab(self.settings_tab, "Paramètres")

        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _go_generate_revision(self, subject_id, context_text):
        self.tabs.setCurrentWidget(self.revision_tab)
        self.revision_tab.generate_for_context(subject_id, context_text)

    def _go_generate_exercises(self, subject_id, context_text):
        self.tabs.setCurrentWidget(self.sandbox_tab)
        self.sandbox_tab.generate_for_context(subject_id, context_text)
