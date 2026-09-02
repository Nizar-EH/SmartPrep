from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox, QPushButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from collections import defaultdict


class StatsTab(QWidget):
    """Graphiques de l'évolution des notes et de la moyenne générale par trimestre."""

    def __init__(self, db):
        super().__init__()
        self.db = db

        layout = QVBoxLayout(self)
        title = QLabel("Statistiques")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.trimester_filter = QComboBox()
        self.trimester_filter.addItems(["Tous les trimestres", "Trimestre 1", "Trimestre 2", "Trimestre 3"])
        self.trimester_filter.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.trimester_filter)

        refresh_btn = QPushButton("Rafraîchir")
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        self.figure = Figure(figsize=(6, 5))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        self.refresh()

    def refresh(self):
        self.figure.clear()
        evals = self.db.list_evaluations()
        if not evals:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "Aucune évaluation enregistrée pour le moment",
                    ha="center", va="center")
            ax.axis("off")
            self.canvas.draw()
            return

        idx = self.trimester_filter.currentIndex()
        if idx > 0:
            evals = [e for e in evals if e["trimester"] == idx]

        ax1 = self.figure.add_subplot(211)
        dates = [e["date"] for e in evals]
        normalized = [e["grade"] / e["max_grade"] * 20 for e in evals]
        labels = [f"{e['subject_name']}\n{e['title'][:12]}" for e in evals]
        ax1.plot(range(len(evals)), normalized, marker="o")
        ax1.set_xticks(range(len(evals)))
        ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
        ax1.set_ylabel("Note /20")
        ax1.set_title("Évolution des notes")
        ax1.set_ylim(0, 20)
        ax1.grid(True, alpha=0.3)

        # moyenne générale par trimestre
        ax2 = self.figure.add_subplot(212)
        all_evals = self.db.list_evaluations()
        by_trimester = defaultdict(list)
        for e in all_evals:
            by_trimester[e["trimester"]].append(e["grade"] / e["max_grade"] * 20)

        trimesters = sorted(by_trimester.keys())
        averages = [sum(by_trimester[t]) / len(by_trimester[t]) for t in trimesters]
        ax2.bar([f"Trimestre {t}" for t in trimesters], averages, color="#2563eb")
        ax2.set_ylabel("Moyenne /20")
        ax2.set_title("Moyenne générale par trimestre")
        ax2.set_ylim(0, 20)
        for i, v in enumerate(averages):
            ax2.text(i, v + 0.3, f"{v:.1f}", ha="center", fontsize=9)

        self.figure.tight_layout()
        self.canvas.draw()
