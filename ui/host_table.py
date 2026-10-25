"""
Таблица хостов с цветовыми индикаторами статуса,
информацией об ОС/архитектуре и привязкой к логам.
"""

from typing import Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ui.styles import get_status_badge_html


class HostTableWidget(QTableWidget):
    """
    Таблица компьютеров класса.
    По клику на строку отправляет сигнал host_selected(ip) для фильтрации логов.
    """
    host_selected = pyqtSignal(str)

    COL_IP = 0
    COL_HOSTNAME = 1
    COL_OS_ARCH = 2
    COL_STATUS = 3
    COL_PING = 4
    COL_DISK_UPTIME = 5
    COL_DETAILS = 6

    HEADERS = [
        "IP-адрес",
        "Имя хоста",
        "ОС / Архитектура",
        "Статус",
        "Связь",
        "Диск / Аптайм",
        "Детали / Результат",
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)

        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_IP, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_HOSTNAME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_OS_ARCH, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PING, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DISK_UPTIME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DETAILS, QHeaderView.ResizeMode.Stretch)

        self._ip_to_row: Dict[str, int] = {}
        self._host_info: Dict[str, dict] = {}

        self.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item: QTableWidgetItem):
        row = item.row()
        ip_item = self.item(row, self.COL_IP)
        if ip_item:
            self.host_selected.emit(ip_item.text())

    def set_hosts(self, ips: List[str]):
        """Заполняет таблицу списком IP-адресов."""
        self.setRowCount(len(ips))
        self._ip_to_row.clear()
        self._host_info.clear()

        for row, ip in enumerate(ips):
            self._ip_to_row[ip] = row

            item_ip = QTableWidgetItem(ip)
            item_ip.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_IP, item_ip)

            item_host = QTableWidgetItem("—")
            item_host.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_HOSTNAME, item_host)

            item_os = QTableWidgetItem("—")
            item_os.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_OS_ARCH, item_os)

            # Статус в виде виджета с HTML-бейджем
            self._set_status_badge(row, "Ожидание")

            item_ping = QTableWidgetItem("Не проверено")
            item_ping.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_PING, item_ping)

            item_disk = QTableWidgetItem("—")
            item_disk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_DISK_UPTIME, item_disk)

            item_details = QTableWidgetItem("Готов к работе")
            self.setItem(row, self.COL_DETAILS, item_details)

    def _set_status_badge(self, row: int, status_text: str):
        badge_label = QLabel()
        badge_label.setTextFormat(Qt.TextFormat.RichText)
        badge_label.setText(get_status_badge_html(status_text))
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCellWidget(row, self.COL_STATUS, badge_label)

    def update_host_status(self, ip: str, status: str, details: str):
        """Обновляет статус и детали для указанного IP."""
        if ip not in self._ip_to_row:
            return
        row = self._ip_to_row[ip]

        self._set_status_badge(row, status)

        item_details = self.item(row, self.COL_DETAILS)
        if item_details:
            item_details.setText(details)
            if status == "Ошибка":
                item_details.setForeground(QColor("#fb7185"))
            elif status == "Успешно":
                item_details.setForeground(QColor("#a6e3a1"))
            else:
                item_details.setForeground(QColor("#cad3f5"))

        # Обновляем колонку связи
        item_ping = self.item(row, self.COL_PING)
        if item_ping:
            if status == "Успешно":
                item_ping.setText("🟢 Онлайн")
                item_ping.setForeground(QColor("#a6e3a1"))
            elif status == "Ошибка" and "недоступен" in details.lower():
                item_ping.setText("🔴 Офлайн")
                item_ping.setForeground(QColor("#fb7185"))
            elif status == "В процессе":
                item_ping.setText("🟡 Связь...")
                item_ping.setForeground(QColor("#f9e2af"))

    def update_host_info(self, ip: str, info: dict):
        """Обновляет данные об ОС, имени хоста, архитектуре и диске."""
        if ip not in self._ip_to_row:
            return
        row = self._ip_to_row[ip]
        self._host_info[ip] = info

        hostname = info.get("hostname", "")
        if hostname:
            item_h = self.item(row, self.COL_HOSTNAME)
            if item_h:
                item_h.setText(hostname)

        os_name = info.get("os", "")
        arch = info.get("arch", "")
        if os_name or arch:
            item_os = self.item(row, self.COL_OS_ARCH)
            if item_os:
                item_os.setText(f"{os_name} [{arch}]")

        disk = info.get("disk", "")
        uptime = info.get("uptime", "")
        if disk or uptime:
            item_du = self.item(row, self.COL_DISK_UPTIME)
            if item_du:
                item_du.setText(f"Своб: {disk} | {uptime}")

    def get_summary_stats(self) -> dict:
        """Возвращает агрегированную статистику по текущему списку хостов."""
        total = self.rowCount()
        online = 0
        errors = 0
        in_progress = 0

        for row in range(total):
            item_ping = self.item(row, self.COL_PING)
            if item_ping and "Онлайн" in item_ping.text():
                online += 1

            widget = self.cellWidget(row, self.COL_STATUS)
            if isinstance(widget, QLabel):
                txt = widget.text()
                if "Ошибка" in txt:
                    errors += 1
                elif "В процессе" in txt:
                    in_progress += 1

        return {
            "total": total,
            "online": online,
            "errors": errors,
            "in_progress": in_progress,
        }
