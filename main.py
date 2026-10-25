#!/usr/bin/env python3
"""
SchoolAdm — Кроссплатформенное графическое приложение на Python (PyQt6 + Paramiko)
для централизованного администрирования парка школьных компьютеров по SSH/SFTP.

Поддерживаемые ОС: Альт Линукс, Ubuntu, Debian, Astra Linux.
Архитектуры: x86_64, ARM (aarch64).
"""

import os
import sys
import traceback
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow
from ui.styles import DARK_THEME_QSS


def setup_exception_hook():
    """Перехватывает необработанные исключения и выводит читаемый диалог пользователю."""
    def excepthook(exc_type, exc_value, exc_tb):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print("Необработанное исключение:", error_msg, file=sys.stderr)
        
        # Если интерфейс инициализирован, показываем графическое окно ошибки
        if QApplication.instance():
            dlg = QMessageBox()
            dlg.setIcon(QMessageBox.Icon.Critical)
            dlg.setWindowTitle("Критическая ошибка SchoolAdm")
            dlg.setText(f"Произошла непредвиденная ошибка:\n{exc_value}")
            dlg.setDetailedText(error_msg)
            dlg.exec()
        else:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = excepthook


def main():
    setup_exception_hook()

    app = QApplication(sys.argv)
    app.setApplicationName("SchoolAdm")
    app.setOrganizationName("SchoolLab")
    app.setApplicationDisplayName("SchoolAdm — Центр управления компьютерным классом")

    # Установка иконки приложения
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "schooladm.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Применяем современную темную тему
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
