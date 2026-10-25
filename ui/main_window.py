"""
Главное окно приложения SchoolAdm на PyQt6.
Интегрирует блок подключения, выбор ОС/архитектуры, действия,
таблицу хостов и консоль терминала.
"""

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config.settings import (
    ARCH_ARM,
    ARCH_X86_64,
    OS_ALT_LINUX,
    OS_ASTRA_LINUX,
    OS_DEBIAN,
    OS_UBUNTU,
    SUPPORTED_ARCH,
    SUPPORTED_OS,
    ClassroomProfile,
    ProfileManager,
)
from core.ip_parser import parse_ip_targets
from core.task_runner import AsyncTaskThread
from ui.dialogs import (
    ConfirmActionDialog,
    FileTransferDialog,
    RunCommandDialog,
    RunExistingFileDialog,
    SaveProfileDialog,
)
from ui.host_table import HostTableWidget
from ui.log_viewer import LogViewerWidget


class MainWindow(QMainWindow):
    """Основное окно графического интерфейса администратора."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SchoolAdm — Панель администрирования компьютерного класса (SSH/SFTP)")
        self.resize(1240, 820)
        self.setMinimumSize(960, 640)

        self.profile_mgr = ProfileManager()
        self.current_task_thread: Optional[AsyncTaskThread] = None

        self._init_ui()
        self._load_profiles_into_ui()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Верхняя панель: Настройки подключения и Выбор ОС/Архитектуры
        top_panel = QHBoxLayout()
        top_panel.setSpacing(10)

        # Блок подключения
        group_conn = self._create_connection_group()
        top_panel.addWidget(group_conn, stretch=3)

        # Блок ОС и архитектуры
        group_os = self._create_os_group()
        top_panel.addWidget(group_os, stretch=1)

        main_layout.addLayout(top_panel)

        # 2. Панель действий (кнопки)
        group_actions = self._create_actions_group()
        main_layout.addWidget(group_actions)

        # 3. Центральный блок: Таблица хостов + Консоль логов (сплиттер)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)

        # Таблица хостов
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        table_header = QHBoxLayout()
        lbl_table = QLabel("Мониторинг клиентских компьютеров")
        lbl_table.setStyleSheet("font-weight: bold; color: #8aadf4; font-size: 13px;")
        table_header.addWidget(lbl_table)

        self.lbl_stats = QLabel("Всего: 0 | Онлайн: 0 | Ошибок: 0")
        self.lbl_stats.setStyleSheet("color: #a5adcb; font-size: 12px;")
        table_header.addWidget(self.lbl_stats, alignment=Qt.AlignmentFlag.AlignRight)
        table_layout.addLayout(table_header)

        self.host_table = HostTableWidget()
        self.host_table.host_selected.connect(self._on_table_host_selected)
        table_layout.addWidget(self.host_table)
        splitter.addWidget(table_container)

        # Консоль логов
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(4)

        self.log_viewer = LogViewerWidget()
        log_layout.addWidget(self.log_viewer)
        splitter.addWidget(log_container)

        # Начальное распределение высот: 55% таблица, 45% консоль
        splitter.setSizes([420, 320])
        main_layout.addWidget(splitter, stretch=1)

        # 4. Статус-бар внизу
        self._init_status_bar()

    def _create_connection_group(self) -> QGroupBox:
        group = QGroupBox("Параметры подключения и целевые ПК")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        # Профили кабинетов
        prof_layout = QHBoxLayout()
        lbl_prof = QLabel("Кабинет (Профиль):")
        lbl_prof.setStyleSheet("font-weight: 600;")
        prof_layout.addWidget(lbl_prof)

        self.cb_profiles = QComboBox()
        self.cb_profiles.currentTextChanged.connect(self._on_profile_selected)
        prof_layout.addWidget(self.cb_profiles, stretch=1)

        self.btn_save_profile = QPushButton("💾 Сохранить")
        self.btn_save_profile.setToolTip("Сохранить текущие параметры в профиль кабинета")
        self.btn_save_profile.clicked.connect(self._save_profile_dialog)
        prof_layout.addWidget(self.btn_save_profile)

        self.btn_del_profile = QPushButton("🗑️ Удалить")
        self.btn_del_profile.setToolTip("Удалить выбранный профиль")
        self.btn_del_profile.clicked.connect(self._delete_current_profile)
        prof_layout.addWidget(self.btn_del_profile)

        layout.addLayout(prof_layout)

        # Строка IP-адресов
        ip_layout = QHBoxLayout()
        lbl_ips = QLabel("IP-адреса ПК:")
        lbl_ips.setFixedWidth(110)
        lbl_ips.setStyleSheet("font-weight: 600;")
        ip_layout.addWidget(lbl_ips)

        self.edit_ips = QLineEdit()
        self.edit_ips.setPlaceholderText("Пример: 192.168.1.10-192.168.1.25, 192.168.1.30, 192.168.1.40-45")
        self.edit_ips.textChanged.connect(self._on_ips_text_changed)
        ip_layout.addWidget(self.edit_ips, stretch=1)

        self.btn_apply_ips = QPushButton("Загрузить в таблицу")
        self.btn_apply_ips.clicked.connect(self._apply_ips_to_table)
        ip_layout.addWidget(self.btn_apply_ips)

        layout.addLayout(ip_layout)

        # Учетные данные (Логин, Пароль с кнопкой скрытия, Порт, Root/Sudo)
        cred_layout = QHBoxLayout()
        cred_layout.setSpacing(10)

        lbl_login = QLabel("Логин:")
        cred_layout.addWidget(lbl_login)
        self.edit_login = QLineEdit("teacher")
        self.edit_login.setFixedWidth(100)
        cred_layout.addWidget(self.edit_login)

        lbl_pass = QLabel("Пароль:")
        cred_layout.addWidget(lbl_pass)
        self.edit_pass = QLineEdit()
        self.edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pass.setFixedWidth(120)
        cred_layout.addWidget(self.edit_pass)

        self.btn_toggle_pass = QPushButton("👁️")
        self.btn_toggle_pass.setFixedWidth(34)
        self.btn_toggle_pass.setToolTip("Показать/скрыть пароль")
        self.btn_toggle_pass.clicked.connect(self._toggle_password_visibility)
        cred_layout.addWidget(self.btn_toggle_pass)

        lbl_port = QLabel("SSH Порт:")
        cred_layout.addWidget(lbl_port)
        self.edit_port = QLineEdit("22")
        self.edit_port.setFixedWidth(50)
        cred_layout.addWidget(self.edit_port)

        cred_layout.addSpacing(10)

        # Переключатель: root / sudo
        self.rb_root = QRadioButton("От root")
        self.rb_sudo = QRadioButton("Через sudo")
        self.rb_sudo.setChecked(True)
        self.bg_priv = QButtonGroup(self)
        self.bg_priv.addButton(self.rb_root)
        self.bg_priv.addButton(self.rb_sudo)

        cred_layout.addWidget(self.rb_root)
        cred_layout.addWidget(self.rb_sudo)
        cred_layout.addStretch()

        layout.addLayout(cred_layout)

        return group

    def _create_os_group(self) -> QGroupBox:
        group = QGroupBox("Целевая ОС и Архитектура")
        form = QFormLayout(group)
        form.setSpacing(8)

        self.cb_os = QComboBox()
        self.cb_os.addItems(SUPPORTED_OS)
        form.addRow("Дистрибутив:", self.cb_os)

        self.cb_arch = QComboBox()
        self.cb_arch.addItems(SUPPORTED_ARCH)
        form.addRow("Архитектура:", self.cb_arch)

        hint = QLabel("Команды обновлений и запуска адаптируются под выбранную ОС.")
        hint.setStyleSheet("color: #6e738d; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(hint)

        return group

    def _create_actions_group(self) -> QGroupBox:
        group = QGroupBox("Действия над компьютерами")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.btn_ping = QPushButton("📡 Проверить доступность (Ping/SSH)")
        self.btn_ping.setObjectName("btn_primary")
        self.btn_ping.clicked.connect(self._action_check_availability)
        row1.addWidget(self.btn_ping)

        self.btn_update = QPushButton("🔄 Обновить систему на всех ПК")
        self.btn_update.setObjectName("btn_warning")
        self.btn_update.clicked.connect(self._action_update_system)
        row1.addWidget(self.btn_update)

        self.btn_upload = QPushButton("📁 Передать файл")
        self.btn_upload.clicked.connect(self._action_upload_file)
        row1.addWidget(self.btn_upload)

        self.btn_upload_run = QPushButton("🚀 Передать и запустить")
        self.btn_upload_run.clicked.connect(self._action_upload_and_run)
        row1.addWidget(self.btn_upload_run)

        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.btn_run_existing = QPushButton("▶️ Запустить существующий файл")
        self.btn_run_existing.clicked.connect(self._action_run_existing)
        row2.addWidget(self.btn_run_existing)

        self.btn_custom_cmd = QPushButton("⌨️ Выполнить произвольную команду")
        self.btn_custom_cmd.clicked.connect(self._action_custom_command)
        row2.addWidget(self.btn_custom_cmd)

        self.btn_reboot = QPushButton("🔁 Перезагрузить все ПК")
        self.btn_reboot.setObjectName("btn_danger")
        self.btn_reboot.clicked.connect(self._action_reboot)
        row2.addWidget(self.btn_reboot)

        self.btn_poweroff = QPushButton("⏻ Выключить все ПК")
        self.btn_poweroff.setObjectName("btn_danger")
        self.btn_poweroff.clicked.connect(self._action_poweroff)
        row2.addWidget(self.btn_poweroff)

        self.btn_cancel_task = QPushButton("⏹️ Остановить")
        self.btn_cancel_task.setEnabled(False)
        self.btn_cancel_task.clicked.connect(self._action_cancel_current_task)
        row2.addWidget(self.btn_cancel_task)

        layout.addLayout(row2)

        return group

    def _init_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_task_status = QLabel("Готов к работе")
        self.status_bar.addWidget(self.lbl_task_status, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(240)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    # ------------------ Управление профилями ------------------

    def _load_profiles_into_ui(self):
        profiles = self.profile_mgr.get_all()
        self.cb_profiles.blockSignals(True)
        self.cb_profiles.clear()
        for p in profiles:
            self.cb_profiles.addItem(p.name)
        self.cb_profiles.blockSignals(False)

        if profiles:
            self._apply_profile(profiles[0])

    def _on_profile_selected(self, name: str):
        prof = self.profile_mgr.get(name)
        if prof:
            self._apply_profile(prof)

    def _apply_profile(self, p: ClassroomProfile):
        self.edit_ips.setText(p.ip_range_text)
        self.edit_login.setText(p.username)
        self.edit_pass.setText(p.password)
        self.edit_port.setText(str(p.port))
        if p.use_sudo:
            self.rb_sudo.setChecked(True)
        else:
            self.rb_root.setChecked(True)

        idx_os = self.cb_os.findText(p.target_os)
        if idx_os >= 0:
            self.cb_os.setCurrentIndex(idx_os)

        idx_arch = self.cb_arch.findText(p.target_arch)
        if idx_arch >= 0:
            self.cb_arch.setCurrentIndex(idx_arch)

        self._apply_ips_to_table()

    def _save_profile_dialog(self):
        cur_name = self.cb_profiles.currentText()
        dlg = SaveProfileDialog(cur_name, self)
        if dlg.exec():
            name, desc = dlg.get_data()
            try:
                port = int(self.edit_port.text().strip() or "22")
            except ValueError:
                port = 22

            prof = ClassroomProfile(
                name=name,
                ip_range_text=self.edit_ips.text().strip(),
                username=self.edit_login.text().strip(),
                password=self.edit_pass.text(),
                port=port,
                use_sudo=self.rb_sudo.isChecked(),
                target_os=self.cb_os.currentText(),
                target_arch=self.cb_arch.currentText(),
                description=desc,
            )
            self.profile_mgr.set(prof)
            self._load_profiles_into_ui()
            idx = self.cb_profiles.findText(name)
            if idx >= 0:
                self.cb_profiles.setCurrentIndex(idx)
            QMessageBox.information(self, "Успешно", f"Профиль «{name}» успешно сохранен.")

    def _delete_current_profile(self):
        name = self.cb_profiles.currentText()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Удаление профиля",
            f"Вы уверены, что хотите удалить профиль «{name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.profile_mgr.delete(name)
            self._load_profiles_into_ui()

    # ------------------ Обработка IP и синхронизация ------------------

    def _on_ips_text_changed(self):
        pass

    def _apply_ips_to_table(self):
        raw_text = self.edit_ips.text()
        ips, errors = parse_ip_targets(raw_text)

        if errors:
            err_msg = "\n".join(errors[:5])
            if len(errors) > 5:
                err_msg += f"\n...и ещё {len(errors) - 5} ошибок."
            QMessageBox.warning(self, "Предупреждение валидации IP", f"Обнаружены некорректные адреса:\n{err_msg}")

        self.host_table.set_hosts(ips)
        self.log_viewer.set_host_list(ips)
        self._update_stats_label()

    def _get_target_ips(self) -> List[str]:
        raw_text = self.edit_ips.text()
        ips, errors = parse_ip_targets(raw_text)
        if not ips:
            QMessageBox.warning(
                self,
                "Нет целевых ПК",
                "Список IP-адресов пуст или содержит только некорректные записи.\n"
                "Введите адреса или выберите профиль кабинета.",
            )
            return []
        return ips

    def _on_table_host_selected(self, ip: str):
        self.log_viewer.set_filter_to_ip(ip)

    def _toggle_password_visibility(self):
        if self.edit_pass.echoMode() == QLineEdit.EchoMode.Password:
            self.edit_pass.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_pass.setText("🙈")
        else:
            self.edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_pass.setText("👁️")

    def _update_stats_label(self):
        stats = self.host_table.get_summary_stats()
        self.lbl_stats.setText(
            f"Всего ПК: {stats['total']}  |  "
            f"Онлайн: <span style='color: #a6e3a1; font-weight: bold;'>{stats['online']}</span>  |  "
            f"Ошибок: <span style='color: #fb7185; font-weight: bold;'>{stats['errors']}</span>"
        )

    # ------------------ Запуск асинхронных задач ------------------

    def _start_task(self, task_type: str, task_name: str, extra_params: Optional[dict] = None):
        ips = self._get_target_ips()
        if not ips:
            return

        # Убедимся, что таблица заполнена этими IP
        if self.host_table.rowCount() != len(ips):
            self.host_table.set_hosts(ips)
            self.log_viewer.set_host_list(ips)

        try:
            port = int(self.edit_port.text().strip() or "22")
        except ValueError:
            port = 22

        # Блокируем кнопки действий
        self._set_ui_busy(True)

        self.current_task_thread = AsyncTaskThread(
            task_type=task_type,
            task_name=task_name,
            ips=ips,
            port=port,
            username=self.edit_login.text().strip(),
            password=self.edit_pass.text(),
            use_sudo=self.rb_sudo.isChecked(),
            target_os=self.cb_os.currentText(),
            target_arch=self.cb_arch.currentText(),
            extra_params=extra_params or {},
        )

        # Подключаем сигналы
        sig = self.current_task_thread.signals
        sig.task_started.connect(self._on_task_started)
        sig.host_status_changed.connect(self._on_host_status_changed)
        sig.host_info_updated.connect(self._on_host_info_updated)
        sig.host_log.connect(self._on_host_log)
        sig.progress_updated.connect(self._on_progress_updated)
        sig.task_finished.connect(self._on_task_finished)

        self.current_task_thread.start()

    def _set_ui_busy(self, is_busy: bool):
        self.btn_ping.setEnabled(not is_busy)
        self.btn_update.setEnabled(not is_busy)
        self.btn_upload.setEnabled(not is_busy)
        self.btn_upload_run.setEnabled(not is_busy)
        self.btn_run_existing.setEnabled(not is_busy)
        self.btn_custom_cmd.setEnabled(not is_busy)
        self.btn_reboot.setEnabled(not is_busy)
        self.btn_poweroff.setEnabled(not is_busy)
        self.btn_apply_ips.setEnabled(not is_busy)
        self.btn_cancel_task.setEnabled(is_busy)
        self.progress_bar.setVisible(is_busy)

    def _on_task_started(self, task_name: str, total_hosts: int):
        self.lbl_task_status.setText(f"Выполняется задача: «{task_name}» на {total_hosts} ПК...")
        self.progress_bar.setMaximum(total_hosts)
        self.progress_bar.setValue(0)

    def _on_host_status_changed(self, ip: str, status: str, details: str):
        self.host_table.update_host_status(ip, status, details)
        self._update_stats_label()

    def _on_host_info_updated(self, ip: str, info: dict):
        self.host_table.update_host_info(ip, info)

    def _on_host_log(self, ip: str, stream_type: str, message: str):
        self.log_viewer.append_log(ip, stream_type, message)

    def _on_progress_updated(self, completed: int, total: int):
        self.progress_bar.setValue(completed)
        self._update_stats_label()

    def _on_task_finished(self, task_name: str, success_count: int, fail_count: int):
        self._set_ui_busy(False)
        self.lbl_task_status.setText(f"Задача «{task_name}» завершена. Успешно: {success_count}, Ошибок: {fail_count}.")
        self._update_stats_label()

        QMessageBox.information(
            self,
            "Задача завершена",
            f"Задача «{task_name}» завершена.\n\n"
            f"🟢 Успешно: {success_count}\n"
            f"🔴 С ошибками: {fail_count}\n\n"
            f"Подробности смотрите в таблице и консоли логов.",
        )

    # ------------------ Действия кнопок ------------------

    def _action_check_availability(self):
        self._start_task("CHECK_AVAILABILITY", "Проверка доступности (Ping/SSH)")

    def _action_update_system(self):
        ips = self._get_target_ips()
        if not ips:
            return

        os_name = self.cb_os.currentText()
        dlg = ConfirmActionDialog(
            title="Подтверждение обновления системы",
            action_name=f"Массовое обновление ПО ({os_name})",
            host_count=len(ips),
            warning_text="Обновление пакетов потребляет интернет-трафик и дисковое пространство на всех компьютерах.",
            is_dangerous=False,
            parent=self,
        )
        if dlg.exec():
            self._start_task("UPDATE_SYSTEM", f"Обновление системы ({os_name})")

    def _action_upload_file(self):
        ips = self._get_target_ips()
        if not ips:
            return

        dlg = FileTransferDialog(and_run=False, default_user=self.edit_login.text(), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            self._start_task("UPLOAD_FILE", "Передача файла по SFTP", extra_params=data)

    def _action_upload_and_run(self):
        ips = self._get_target_ips()
        if not ips:
            return

        dlg = FileTransferDialog(and_run=True, default_user=self.edit_login.text(), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            self._start_task("UPLOAD_AND_RUN", "Передача и запуск файла", extra_params=data)

    def _action_run_existing(self):
        ips = self._get_target_ips()
        if not ips:
            return

        dlg = RunExistingFileDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            self._start_task("RUN_EXISTING", "Запуск существующего файла", extra_params=data)

    def _action_custom_command(self):
        ips = self._get_target_ips()
        if not ips:
            return

        dlg = RunCommandDialog(self)
        if dlg.exec():
            cmd = dlg.get_command()
            self._start_task("EXECUTE_COMMAND", "Произвольная команда", extra_params={"command": cmd})

    def _action_reboot(self):
        ips = self._get_target_ips()
        if not ips:
            return

        dlg = ConfirmActionDialog(
            title="Подтверждение перезагрузки",
            action_name="Перезагрузка всех клиентских ПК",
            host_count=len(ips),
            warning_text="Внимание! Все несохраненные данные учащихся будут утеряны. Компьютеры будут немедленно перезагружены.",
            is_dangerous=True,
            parent=self,
        )
        if dlg.exec():
            self._start_task("REBOOT", "Перезагрузка ПК")

    def _action_poweroff(self):
        ips = self._get_target_ips()
        if not ips:
            return

        dlg = ConfirmActionDialog(
            title="Подтверждение выключения",
            action_name="Выключение всех клиентских ПК (poweroff)",
            host_count=len(ips),
            warning_text="Внимание! Все клиентские компьютеры завершат работу и выключатся. Для повторного включения потребуется Wake-on-LAN или физическое включение.",
            is_dangerous=True,
            parent=self,
        )
        if dlg.exec():
            self._start_task("POWEROFF", "Выключение ПК")

    def _action_cancel_current_task(self):
        if self.current_task_thread and self.current_task_thread.isRunning():
            self.current_task_thread.cancel()
            self.lbl_task_status.setText("Запрос на отмену задачи отправлен...")
            self.btn_cancel_task.setEnabled(False)
