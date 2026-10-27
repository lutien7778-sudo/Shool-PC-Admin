"""
Главное окно приложения SchoolAdm на PyQt6.
Интегрирует блок подключения, выбор ОС/архитектуры, действия,
таблицу хостов с индивидуальными кредами, быструю командную строку и консоль терминала.
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
        self.resize(1280, 840)
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

        # 2. Панель действий (кнопки и переключатель режима выполнения)
        group_actions = self._create_actions_group()
        main_layout.addWidget(group_actions)

        # 3. Центральный блок: Таблица хостов + Быстрая командная строка + Консоль логов (сплиттер)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)

        # Таблица хостов
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)

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
        self.host_table.itemSelectionChanged.connect(self._update_stats_label)
        self.host_table.context_action_requested.connect(self._handle_context_action)
        table_layout.addWidget(self.host_table)

        # Интерактивная строка ввода команд под таблицей
        quick_cmd_layout = QHBoxLayout()
        quick_cmd_layout.setSpacing(6)

        lbl_cmd = QLabel("Быстрая команда:")
        lbl_cmd.setStyleSheet("font-weight: 600; color: #8aadf4;")
        quick_cmd_layout.addWidget(lbl_cmd)

        self.edit_quick_cmd = QLineEdit()
        self.edit_quick_cmd.setPlaceholderText("Введите bash-команду (например: uptime, free -h, df -h, ls -la /tmp)...")
        self.edit_quick_cmd.returnPressed.connect(self._on_quick_cmd_send)
        quick_cmd_layout.addWidget(self.edit_quick_cmd, stretch=1)

        self.cb_cmd_target = QComboBox()
        self.cb_cmd_target.addItems([
            "Цель: Выбранный в таблице ПК",
            "Цель: Все ПК",
        ])
        quick_cmd_layout.addWidget(self.cb_cmd_target)

        self.btn_send_cmd = QPushButton("🚀 Отправить")
        self.btn_send_cmd.setObjectName("btn_primary")
        self.btn_send_cmd.clicked.connect(self._on_quick_cmd_send)
        quick_cmd_layout.addWidget(self.btn_send_cmd)

        table_layout.addLayout(quick_cmd_layout)

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

        # Переключатель: Общие / Раздельные учетные данные для каждого ПК
        cred_mode_layout = QHBoxLayout()
        lbl_cred_mode = QLabel("Режим учетных данных:")
        lbl_cred_mode.setStyleSheet("font-weight: 600;")
        cred_mode_layout.addWidget(lbl_cred_mode)

        self.rb_common_creds = QRadioButton("Одинаковые учетные данные для всех")
        self.rb_individual_creds = QRadioButton("Раздельные учетные данные для каждого ПК")
        self.rb_common_creds.setChecked(True)
        self.bg_creds = QButtonGroup(self)
        self.bg_creds.addButton(self.rb_common_creds)
        self.bg_creds.addButton(self.rb_individual_creds)

        self.rb_common_creds.toggled.connect(self._on_credential_mode_changed)

        cred_mode_layout.addWidget(self.rb_common_creds)
        cred_mode_layout.addWidget(self.rb_individual_creds)
        cred_mode_layout.addStretch()

        layout.addLayout(cred_mode_layout)

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

        # Переключатель режима выполнения задач (Параллельно / Поочередно)
        mode_exec_layout = QHBoxLayout()
        lbl_exec = QLabel("Режим выполнения задач:")
        lbl_exec.setStyleSheet("font-weight: 600; color: #8aadf4;")
        mode_exec_layout.addWidget(lbl_exec)

        self.rb_mode_parallel = QRadioButton("Параллельно (все ПК)")
        self.rb_mode_seq = QRadioButton("Поочередно (по 1 ПК)")
        self.rb_mode_parallel.setChecked(True)
        self.bg_mode = QButtonGroup(self)
        self.bg_mode.addButton(self.rb_mode_parallel)
        self.bg_mode.addButton(self.rb_mode_seq)

        mode_exec_layout.addWidget(self.rb_mode_parallel)
        mode_exec_layout.addWidget(self.rb_mode_seq)
        mode_exec_layout.addStretch()

        layout.addLayout(mode_exec_layout)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.btn_ping = QPushButton("📡 Проверить доступность (Ping/SSH)")
        self.btn_ping.setObjectName("btn_primary")
        self.btn_ping.clicked.connect(lambda: self._action_check_availability())
        row1.addWidget(self.btn_ping)

        self.btn_update = QPushButton("🔄 Обновить систему на ПК")
        self.btn_update.setObjectName("btn_warning")
        self.btn_update.clicked.connect(lambda: self._action_update_system())
        row1.addWidget(self.btn_update)

        self.btn_upload = QPushButton("📁 Передать файл")
        self.btn_upload.clicked.connect(lambda: self._action_upload_file())
        row1.addWidget(self.btn_upload)

        self.btn_upload_run = QPushButton("🚀 Передать и запустить")
        self.btn_upload_run.clicked.connect(lambda: self._action_upload_and_run())
        row1.addWidget(self.btn_upload_run)

        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.btn_run_existing = QPushButton("▶️ Запустить существующий файл")
        self.btn_run_existing.clicked.connect(lambda: self._action_run_existing())
        row2.addWidget(self.btn_run_existing)

        self.btn_custom_cmd = QPushButton("⌨️ Выполнить произвольную команду")
        self.btn_custom_cmd.clicked.connect(lambda: self._action_custom_command())
        row2.addWidget(self.btn_custom_cmd)

        self.btn_reboot = QPushButton("🔁 Перезагрузить ПК")
        self.btn_reboot.setObjectName("btn_danger")
        self.btn_reboot.clicked.connect(lambda: self._action_reboot())
        row2.addWidget(self.btn_reboot)

        self.btn_poweroff = QPushButton("⏻ Выключить ПК")
        self.btn_poweroff.setObjectName("btn_danger")
        self.btn_poweroff.clicked.connect(lambda: self._action_poweroff())
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

        use_ind = getattr(p, "use_individual_credentials", False)
        if use_ind:
            self.rb_individual_creds.setChecked(True)
        else:
            self.rb_common_creds.setChecked(True)

        exec_mode = getattr(p, "execution_mode", "parallel")
        if exec_mode == "sequential":
            self.rb_mode_seq.setChecked(True)
        else:
            self.rb_mode_parallel.setChecked(True)

        idx_os = self.cb_os.findText(p.target_os)
        if idx_os >= 0:
            self.cb_os.setCurrentIndex(idx_os)

        idx_arch = self.cb_arch.findText(p.target_arch)
        if idx_arch >= 0:
            self.cb_arch.setCurrentIndex(idx_arch)

        # Заполняем таблицу хостов данными профиля
        ips, _ = parse_ip_targets(p.ip_range_text)
        self.host_table.set_hosts(
            ips,
            host_credentials=getattr(p, "host_credentials", {}),
            default_login=p.username,
            default_password=p.password,
        )
        self.host_table.set_individual_credentials_mode(
            use_ind,
            default_login=p.username,
            default_password=p.password,
        )
        self.log_viewer.set_host_list(ips)
        self._update_stats_label()

    def _save_profile_dialog(self):
        cur_name = self.cb_profiles.currentText()
        dlg = SaveProfileDialog(cur_name, self)
        if dlg.exec():
            name, desc = dlg.get_data()
            try:
                port = int(self.edit_port.text().strip() or "22")
            except ValueError:
                port = 22

            use_ind = self.rb_individual_creds.isChecked()
            host_creds = self.host_table.get_host_credentials() if use_ind else {}
            exec_mode = "sequential" if self.rb_mode_seq.isChecked() else "parallel"

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
                use_individual_credentials=use_ind,
                host_credentials=host_creds,
                execution_mode=exec_mode,
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

    def _on_credential_mode_changed(self):
        is_ind = self.rb_individual_creds.isChecked()
        self.host_table.set_individual_credentials_mode(
            is_ind,
            default_login=self.edit_login.text().strip(),
            default_password=self.edit_pass.text(),
        )

    def _apply_ips_to_table(self):
        raw_text = self.edit_ips.text()
        ips, errors = parse_ip_targets(raw_text)

        if errors:
            err_msg = "\n".join(errors[:5])
            if len(errors) > 5:
                err_msg += f"\n...и ещё {len(errors) - 5} ошибок."
            QMessageBox.warning(self, "Предупреждение валидации IP", f"Обнаружены некорректные адреса:\n{err_msg}")

        existing_creds = self.host_table.get_host_credentials()
        self.host_table.set_hosts(
            ips,
            host_credentials=existing_creds,
            default_login=self.edit_login.text().strip(),
            default_password=self.edit_pass.text(),
        )
        self.host_table.set_individual_credentials_mode(
            self.rb_individual_creds.isChecked(),
            default_login=self.edit_login.text().strip(),
            default_password=self.edit_pass.text(),
        )
        self.log_viewer.set_host_list(ips)
        self._update_stats_label()

    def _get_target_ips(self, explicit_ips: Optional[List[str]] = None, ignore_selection: bool = False) -> List[str]:
        """
        Возвращает целевые IP-адреса.
        Если explicit_ips передан — возвращает его.
        Если в таблице выделены строки и ignore_selection=False — возвращает только выделенные ПК.
        Если ничего не выделено — возвращает все хосты.
        """
        if explicit_ips:
            return explicit_ips

        if not ignore_selection:
            selected = self.host_table.get_selected_ips()
            if selected:
                return selected

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
        selected_count = len(self.host_table.get_selected_ips())
        sel_text = f"  |  Выделено: <span style='color: #8aadf4; font-weight: bold;'>{selected_count}</span>" if selected_count > 0 else ""
        self.lbl_stats.setText(
            f"Всего ПК: {stats['total']}{sel_text}  |  "
            f"Онлайн: <span style='color: #a6e3a1; font-weight: bold;'>{stats['online']}</span>  |  "
            f"Ошибок: <span style='color: #fb7185; font-weight: bold;'>{stats['errors']}</span>"
        )

    # ------------------ Запуск асинхронных задач ------------------

    def _start_task(
        self,
        task_type: str,
        task_name: str,
        extra_params: Optional[dict] = None,
        target_ips: Optional[List[str]] = None,
    ):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        # Заполняем таблицу хостов только если она пуста
        if self.host_table.rowCount() == 0:
            all_ips = self._get_target_ips(ignore_selection=True)
            self.host_table.set_hosts(
                all_ips,
                default_login=self.edit_login.text().strip(),
                default_password=self.edit_pass.text(),
            )
            self.log_viewer.set_host_list(all_ips)

        try:
            port = int(self.edit_port.text().strip() or "22")
        except ValueError:
            port = 22

        self._set_ui_busy(True)

        # Индивидуальные учетные данные при включенном раздельном режиме
        host_creds = None
        if self.rb_individual_creds.isChecked():
            host_creds = self.host_table.get_host_credentials()

        exec_mode = "sequential" if self.rb_mode_seq.isChecked() else "parallel"

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
            execution_mode=exec_mode,
            extra_params=extra_params or {},
            host_credentials=host_creds,
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
        self.btn_send_cmd.setEnabled(not is_busy)
        self.edit_quick_cmd.setEnabled(not is_busy)
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

    # ------------------ Контекстные действия ------------------

    def _handle_context_action(self, action_name: str, ips: List[str]):
        if action_name == "ping":
            self._action_check_availability(target_ips=ips)
        elif action_name == "custom_command":
            self._action_custom_command(target_ips=ips)
        elif action_name == "upload":
            self._action_upload_file(target_ips=ips)
        elif action_name == "reboot":
            self._action_reboot(target_ips=ips)
        elif action_name == "poweroff":
            self._action_poweroff(target_ips=ips)

    # ------------------ Интерактивная командная строка ------------------

    def _on_quick_cmd_send(self):
        cmd = self.edit_quick_cmd.text().strip()
        if not cmd:
            return

        if self.cb_cmd_target.currentIndex() == 0:
            # Цель: Выбранный в таблице ПК
            targets = self.host_table.get_selected_ips()
            if not targets:
                QMessageBox.warning(
                    self,
                    "Цель не выбрана",
                    "В таблице не выделен ни один компьютер.\n"
                    "Выделите строку компьютера в таблице либо выберите цель «Цель: Все ПК».",
                )
                return
        else:
            # Цель: Все ПК
            targets = self._get_target_ips(ignore_selection=True)
            if not targets:
                return

        # Если выбран один хост, фильтруем консоль логов по нему
        if len(targets) == 1:
            self.log_viewer.set_filter_to_ip(targets[0])

        is_bg = cmd.endswith("&") or "DISPLAY=" in cmd
        short_label = cmd[:25] + "..." if len(cmd) > 25 else cmd
        self._start_task(
            "EXECUTE_COMMAND",
            f"Команда: {short_label}",
            extra_params={"command": cmd, "run_in_background": is_bg},
            target_ips=targets,
        )

    # ------------------ Действия кнопок ------------------

    def _action_check_availability(self, target_ips: Optional[List[str]] = None):
        self._start_task("CHECK_AVAILABILITY", "Проверка доступности (Ping/SSH)", target_ips=target_ips)

    def _action_update_system(self, target_ips: Optional[List[str]] = None):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        os_name = self.cb_os.currentText()
        count_desc = f"выделенных ПК ({len(ips)} шт.)" if len(ips) != self.host_table.rowCount() else "всех ПК"
        dlg = ConfirmActionDialog(
            title="Подтверждение обновления системы",
            action_name=f"Массовое обновление ПО ({os_name}) на {count_desc}",
            host_count=len(ips),
            warning_text="Обновление пакетов потребляет интернет-трафик и дисковое пространство на выбранных компьютерах.",
            is_dangerous=False,
            parent=self,
        )
        if dlg.exec():
            self._start_task("UPDATE_SYSTEM", f"Обновление системы ({os_name})", target_ips=ips)

    def _action_upload_file(self, target_ips: Optional[List[str]] = None):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        dlg = FileTransferDialog(and_run=False, default_user=self.edit_login.text(), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            self._start_task("UPLOAD_FILE", "Передача файла по SFTP", extra_params=data, target_ips=ips)

    def _action_upload_and_run(self, target_ips: Optional[List[str]] = None):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        dlg = FileTransferDialog(and_run=True, default_user=self.edit_login.text(), parent=self)
        if dlg.exec():
            data = dlg.get_data()
            self._start_task("UPLOAD_AND_RUN", "Передача и запуск файла", extra_params=data, target_ips=ips)

    def _action_run_existing(self, target_ips: Optional[List[str]] = None):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        dlg = RunExistingFileDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            self._start_task("RUN_EXISTING", "Запуск существующего файла", extra_params=data, target_ips=ips)

    def _action_custom_command(self, target_ips: Optional[List[str]] = None):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        dlg = RunCommandDialog(self)
        if dlg.exec():
            cmd = dlg.get_command()
            self._start_task("EXECUTE_COMMAND", "Произвольная команда", extra_params={"command": cmd}, target_ips=ips)

    def _action_reboot(self, target_ips: Optional[List[str]] = None):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        count_desc = f"выделенных ПК ({len(ips)} шт.)" if len(ips) != self.host_table.rowCount() else "всех клиентских ПК"
        dlg = ConfirmActionDialog(
            title="Подтверждение перезагрузки",
            action_name=f"Перезагрузка {count_desc}",
            host_count=len(ips),
            warning_text="Внимание! Все несохраненные данные учащихся будут утеряны. Компьютеры будут немедленно перезагружены.",
            is_dangerous=True,
            parent=self,
        )
        if dlg.exec():
            self._start_task("REBOOT", "Перезагрузка ПК", target_ips=ips)

    def _action_poweroff(self, target_ips: Optional[List[str]] = None):
        ips = self._get_target_ips(explicit_ips=target_ips)
        if not ips:
            return

        count_desc = f"выделенных ПК ({len(ips)} шт.)" if len(ips) != self.host_table.rowCount() else "всех клиентских ПК"
        dlg = ConfirmActionDialog(
            title="Подтверждение выключения",
            action_name=f"Выключение {count_desc} (poweroff)",
            host_count=len(ips),
            warning_text="Внимание! Все клиентские компьютеры завершат работу и выключатся. Для повторного включения потребуется Wake-on-LAN или физическое включение.",
            is_dangerous=True,
            parent=self,
        )
        if dlg.exec():
            self._start_task("POWEROFF", "Выключение ПК", target_ips=ips)

    def _action_cancel_current_task(self):
        if self.current_task_thread and self.current_task_thread.isRunning():
            self.current_task_thread.cancel()
            self.lbl_task_status.setText("Запрос на отмену задачи отправлен...")
            self.btn_cancel_task.setEnabled(False)
