import sys
from PyQt6.QtWidgets import QApplication

from db import Database
from ui.onboarding import OnboardingDialog
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    db = Database()

    if db.get_profile() is None:
        onboarding = OnboardingDialog(db)
        if onboarding.exec() != onboarding.DialogCode.Accepted:
            sys.exit(0)

    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
