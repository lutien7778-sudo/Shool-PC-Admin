"""
Консоль логов с поддержкой цветового форматирования stdout/stderr,
фильтрацией по хостам, поиском, экспортом и автопрокруткой.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogViewerWidget(QWidget):
    """
    Виджет журнала событий (консоль терминала).
    Позволяет просматривать общий поток сообщений либо вывод конкретного ПК.
    """

    ALL_HOSTS_OPTION = "Все компьютеры (Сводный)"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._all_logs: List[Tuple[str, str, str]] = []  # (ip, stream_type, message)
        self._logs_by_ip: Dict[str, List[Tuple[str, str]]] = {}  # ip -> [(stream_type, message)]
        self._current_filter: str = self.ALL_HOSTS_OPTION

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Верхняя панель управления логом
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        lbl_filter = QLabel("Фильтр вывода:")
        lbl_filter.setStyleSheet("font-weight: 600; color: #8aadf4;")
        toolbar.addWidget(lbl_filter)

        self.cb_filter = QComboBox()
        self.cb_filter.addItem(self.ALL_HOSTS_OPTION)
        self.cb_filter.setMinimumWidth(220)
        self.cb_filter.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.cb_filter)

        self.chk_autoscroll = QCheckBox("Автопрокрутка")
        self.chk_autoscroll.setChecked(True)
        toolbar.addWidget(self.chk_autoscroll)

        toolbar.addStretch()

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.clicked.connect(self.clear_logs)
        toolbar.addWidget(self.btn_clear)

        self.btn_copy = QPushButton("Копировать")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        toolbar.addWidget(self.btn_copy)

        self.btn_export = QPushButton("Сохранить в файл...")
        self.btn_export.clicked.connect(self.export_to_file)
        toolbar.addWidget(self.btn_export)

        layout.addLayout(toolbar)

        # Текстовое поле консоли
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("log_console")
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

    def set_host_list(self, ips: List[str]):
        """Обновляет список доступных фильтров по IP."""
        current = self.cb_filter.currentText()
        self.cb_filter.blockSignals(True)
        self.cb_filter.clear()
        self.cb_filter.addItem(self.ALL_HOSTS_OPTION)
        for ip in ips:
            self.cb_filter.addItem(ip)
            if ip not in self._logs_by_ip:
                self._logs_by_ip[ip] = []

        # Восстанавливаем выбранный фильтр если возможно
        idx = self.cb_filter.findText(current)
        if idx >= 0:
            self.cb_filter.setCurrentIndex(idx)
        else:
            self.cb_filter.setCurrentIndex(0)
        self.cb_filter.blockSignals(False)

    def append_log(self, ip: str, stream_type: str, message: str):
        """
        Добавляет строку в базу логов и отображает её, если она соответствует фильтру.
        stream_type: 'out', 'err', 'info'
        """
        self._all_logs.append((ip, stream_type, message))
        if ip not in self._logs_by_ip:
            self._logs_by_ip[ip] = []
            if self.cb_filter.findText(ip) == -1:
                self.cb_filter.addItem(ip)
        self._logs_by_ip[ip].append((stream_type, message))

        # Проверяем, нужно ли выводить прямо сейчас
        if self._current_filter == self.ALL_HOSTS_OPTION or self._current_filter == ip:
            self._render_log_line(stream_type, message)

    def _render_log_line(self, stream_type: str, message: str):
        color_map = {
            "out": "#cad3f5",   # обычный вывод stdout
            "err": "#f38ba8",   # ошибки stderr
            "info": "#89dceb",  # информационные системные сообщения
        }
        color = color_map.get(stream_type, "#cad3f5")

        # Безопасное экранирование HTML
        safe_msg = (
            message.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace(" ", "&nbsp;")
        )

        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f'<div style="color: {color}; margin: 1px 0; font-family: monospace;">{safe_msg}</div>')

        if self.chk_autoscroll.isChecked():
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def _on_filter_changed(self, text: str):
        self._current_filter = text
        self._rebuild_display()

    def set_filter_to_ip(self, ip: str):
        """Переключает фильтр на указанный IP (например, при клике в таблице)."""
        idx = self.cb_filter.findText(ip)
        if idx >= 0:
            self.cb_filter.setCurrentIndex(idx)

    def _rebuild_display(self):
        """Перерисовывает содержимое консоли под выбранный фильтр."""
        self.text_edit.clear()
        if self._current_filter == self.ALL_HOSTS_OPTION:
            lines = [(st, msg) for _, st, msg in self._all_logs]
        else:
            lines = self._logs_by_ip.get(self._current_filter, [])

        for st, msg in lines:
            self._render_log_line(st, msg)

    def clear_logs(self):
        """Очищает историю логов."""
        self._all_logs.clear()
        self._logs_by_ip.clear()
        self.text_edit.clear()

    def copy_to_clipboard(self):
        """Копирует текущее содержимое консоли в буфер обмена."""
        text = self.text_edit.toPlainText()
        if text:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)

    def export_to_file(self):
        """Экспортирует логи в текстовый файл."""
        text = self.text_edit.toPlainText()
        if not text:
            QMessageBox.information(self, "Информация", "Лог пуст, нечего сохранять.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить лог в файл",
            f"schooladm_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Текстовые файлы (*.txt);;Все файлы (*.*)",
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(text)
                QMessageBox.information(self, "Успешно", f"Лог сохранен в:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось записать файл:\n{str(e)}")
