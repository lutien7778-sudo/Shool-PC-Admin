"""
Таблица хостов с цветовыми индикаторами статуса,
информацией об ОС/архитектуре, индивидуальными учетными данными,
контекстным меню и множественным выделением строк.
"""

from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ui.styles import get_status_badge_html


class HostTableWidget(QTableWidget):
    """
    Таблица компьютеров класса.
    Поддерживает:
    - Выделение одной или нескольких строк (SelectRows, ExtendedSelection)
    - Индивидуальные логины и пароли (скрываемые/отображаемые столбцы)
    - Контекстное меню по правому клику (Проверить связь, Команда, Передать файл, Перезагрузить, Выключить)
    - Сигналы выбора хоста и запроса контекстных действий
    """
    host_selected = pyqtSignal(str)
    context_action_requested = pyqtSignal(str, list)  # action_name, list_of_ips

    COL_IP = 0
    COL_HOSTNAME = 1
    COL_LOGIN = 2
    COL_PASSWORD = 3
    COL_OS_ARCH = 4
    COL_STATUS = 5
    COL_PING = 6
    COL_DISK_UPTIME = 7
    COL_DETAILS = 8

    HEADERS = [
        "IP-адрес",
        "Имя хоста",
        "Логин",
        "Пароль",
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
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)

        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_IP, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_HOSTNAME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_LOGIN, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(self.COL_LOGIN, 110)
        header.setSectionResizeMode(self.COL_PASSWORD, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(self.COL_PASSWORD, 150)
        header.setSectionResizeMode(self.COL_OS_ARCH, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PING, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DISK_UPTIME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DETAILS, QHeaderView.ResizeMode.Stretch)

        self._individual_mode = False
        self._ip_to_row: Dict[str, int] = {}
        self._host_info: Dict[str, dict] = {}
        self._host_inputs: Dict[str, Tuple[QLineEdit, QLineEdit]] = {}

        # По умолчанию скрываем столбцы индивидуальных логинов/паролей
        self.setColumnHidden(self.COL_LOGIN, True)
        self.setColumnHidden(self.COL_PASSWORD, True)

        self.itemClicked.connect(self._on_item_clicked)

        # Контекстное меню
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_custom_context_menu)

    def _on_item_clicked(self, item: QTableWidgetItem):
        row = item.row()
        ip_item = self.item(row, self.COL_IP)
        if ip_item:
            self.host_selected.emit(ip_item.text())

    def _on_custom_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        row = item.row()
        selected_rows = set(idx.row() for idx in self.selectedIndexes())
        if row not in selected_rows:
            self.selectRow(row)

        ips = self.get_selected_ips()
        if not ips:
            return

        menu = QMenu(self)
        act_ping = menu.addAction("📡 Проверить связь")
        act_cmd = menu.addAction("⌨️ Выполнить произвольную команду...")
        act_upload = menu.addAction("📁 Передать файл...")
        menu.addSeparator()
        act_reboot = menu.addAction("🔁 Перезагрузить")
        act_poweroff = menu.addAction("⏻ Выключить")

        action = menu.exec(self.viewport().mapToGlobal(pos))
        if not action:
            return

        if action == act_ping:
            self.context_action_requested.emit("ping", ips)
        elif action == act_cmd:
            self.context_action_requested.emit("custom_command", ips)
        elif action == act_upload:
            self.context_action_requested.emit("upload", ips)
        elif action == act_reboot:
            self.context_action_requested.emit("reboot", ips)
        elif action == act_poweroff:
            self.context_action_requested.emit("poweroff", ips)

    def get_selected_ips(self) -> List[str]:
        """Возвращает список IP-адресов выделенных строк."""
        selected_rows = sorted(set(idx.row() for idx in self.selectedIndexes()))
        ips = []
        for r in selected_rows:
            ip_item = self.item(r, self.COL_IP)
            if ip_item and ip_item.text():
                ips.append(ip_item.text())
        return ips

    def set_individual_credentials_mode(self, enabled: bool, default_login: str = "", default_password: str = ""):
        """Переключает видимость столбцов индивидуальных учетных данных."""
        self._individual_mode = enabled
        self.setColumnHidden(self.COL_LOGIN, not enabled)
        self.setColumnHidden(self.COL_PASSWORD, not enabled)

        if enabled:
            # Заполняем пустые поля значениями по умолчанию
            for ip, (login_edit, pass_edit) in self._host_inputs.items():
                if not login_edit.text() and default_login:
                    login_edit.setText(default_login)
                if not pass_edit.text() and default_password:
                    pass_edit.setText(default_password)

    def set_hosts(
        self,
        ips: List[str],
        host_credentials: Optional[Dict[str, Dict[str, str]]] = None,
        default_login: str = "",
        default_password: str = "",
    ):
        """Заполняет таблицу списком IP-адресов и учетными данными."""
        self.setRowCount(len(ips))
        self._ip_to_row.clear()
        self._host_info.clear()
        self._host_inputs.clear()

        host_creds = host_credentials or {}

        for row, ip in enumerate(ips):
            self._ip_to_row[ip] = row

            item_ip = QTableWidgetItem(ip)
            item_ip.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_IP, item_ip)

            item_host = QTableWidgetItem("—")
            item_host.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_HOSTNAME, item_host)

            # Редактируемый логин
            login_edit = QLineEdit()
            login_edit.setPlaceholderText("Логин")
            user_val = host_creds.get(ip, {}).get("username", default_login)
            login_edit.setText(user_val)
            self.setCellWidget(row, self.COL_LOGIN, login_edit)

            # Редактируемый пароль с кнопкой скрытия/показа
            pass_container = QWidget()
            pass_layout = QHBoxLayout(pass_container)
            pass_layout.setContentsMargins(2, 2, 2, 2)
            pass_layout.setSpacing(2)

            pass_edit = QLineEdit()
            pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
            pass_edit.setPlaceholderText("Пароль")
            pass_val = host_creds.get(ip, {}).get("password", default_password)
            pass_edit.setText(pass_val)
            pass_layout.addWidget(pass_edit)

            btn_peek = QPushButton("👁️")
            btn_peek.setFixedWidth(28)
            btn_peek.setToolTip("Показать/скрыть пароль")

            def make_toggle(pe: QLineEdit, bp: QPushButton):
                def toggle():
                    if pe.echoMode() == QLineEdit.EchoMode.Password:
                        pe.setEchoMode(QLineEdit.EchoMode.Normal)
                        bp.setText("🙈")
                    else:
                        pe.setEchoMode(QLineEdit.EchoMode.Password)
                        bp.setText("👁️")
                return toggle

            btn_peek.clicked.connect(make_toggle(pass_edit, btn_peek))
            pass_layout.addWidget(btn_peek)

            self.setCellWidget(row, self.COL_PASSWORD, pass_container)
            self._host_inputs[ip] = (login_edit, pass_edit)

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

        # Синхронизируем видимость колонок логина и пароля
        self.setColumnHidden(self.COL_LOGIN, not self._individual_mode)
        self.setColumnHidden(self.COL_PASSWORD, not self._individual_mode)

    def get_host_credentials(self) -> Dict[str, Dict[str, str]]:
        """Возвращает индивидуальные логины и пароли всех хостов таблицы."""
        result = {}
        for ip, (login_edit, pass_edit) in self._host_inputs.items():
            result[ip] = {
                "username": login_edit.text().strip(),
                "password": pass_edit.text(),
            }
        return result

    def get_credentials_for_host(self, ip: str) -> Optional[Dict[str, str]]:
        """Возвращает учетные данные конкретного хоста."""
        if ip in self._host_inputs:
            login_edit, pass_edit = self._host_inputs[ip]
            return {
                "username": login_edit.text().strip(),
                "password": pass_edit.text(),
            }
        return None

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
