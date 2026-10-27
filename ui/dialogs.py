"""
Диалоговые окна приложения:
- Подтверждение опасных/массовых операций (reboot, poweroff, update)
- Передача файлов по SFTP и запуск
- Запуск существующего файла на удаленных ПК
- Ввод произвольной shell-команды с предустановленными пресетами
- Создание и редактирование профилей кабинетов
"""

import os
from typing import Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ConfirmActionDialog(QDialog):
    """Диалог обязательного подтверждения действий, затрагивающих множество машин."""

    def __init__(
        self,
        title: str,
        action_name: str,
        host_count: int,
        warning_text: str,
        is_dangerous: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # Заголовок с предупреждением
        header_layout = QHBoxLayout()
        icon_label = QLabel("⚠️" if not is_dangerous else "🚨")
        icon_label.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(icon_label)

        msg_label = QLabel(
            f"<b>Вы собираетесь выполнить:</b><br>"
            f"<span style='color: #8aadf4; font-size: 15px;'>{action_name}</span><br>"
            f"Количество целевых машин: <b>{host_count}</b>"
        )
        msg_label.setTextFormat(Qt.TextFormat.RichText)
        msg_label.setWordWrap(True)
        header_layout.addWidget(msg_label, stretch=1)
        layout.addLayout(header_layout)

        if warning_text:
            warn_box = QLabel(warning_text)
            warn_box.setStyleSheet(
                "background-color: #36222b; color: #f38ba8; "
                "border: 1px solid #f43f5e; border-radius: 6px; padding: 10px;"
            )
            warn_box.setWordWrap(True)
            layout.addWidget(warn_box)

        # Кнопки ответа
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("Подтвердить и выполнить")
        if is_dangerous:
            self.btn_ok.setObjectName("btn_danger")
        else:
            self.btn_ok.setObjectName("btn_primary")
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)

        layout.addLayout(btn_layout)


class FileTransferDialog(QDialog):
    """Диалог выбора локального файла, пути назначения и параметров запуска."""

    def __init__(
        self,
        and_run: bool = False,
        default_user: str = "root",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.and_run = and_run
        self.default_user = default_user
        self.setWindowTitle("Передать и запустить файл" if and_run else "Передать файл на ПК")
        self.setMinimumWidth(540)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # Выбор локального файла
        file_layout = QHBoxLayout()
        self.edit_local = QLineEdit()
        self.edit_local.setPlaceholderText("Выберите локальный файл...")
        self.edit_local.textChanged.connect(self._auto_update_remote_name)
        file_layout.addWidget(self.edit_local)

        self.btn_browse = QPushButton("Обзор...")
        self.btn_browse.clicked.connect(self._browse_file)
        file_layout.addWidget(self.btn_browse)
        form.addRow("Локальный файл:", file_layout)

        # Путь назначения на удаленных машинах
        self.edit_remote = QLineEdit()
        self.edit_remote.setPlaceholderText("/tmp/myscript.sh")
        form.addRow("Удаленный путь назначения:", self.edit_remote)

        layout.addLayout(form)

        # Блок параметров запуска, если режим 'Передать и запустить'
        if self.and_run:
            run_group = QGroupBox("Параметры выполнения после загрузки (chmod +x)")
            run_layout = QVBoxLayout(run_group)
            run_layout.setSpacing(8)

            arg_form = QFormLayout()
            self.edit_args = QLineEdit()
            self.edit_args.setPlaceholderText("Необязательные аргументы (например: --silent -v)")
            arg_form.addRow("Аргументы запуска:", self.edit_args)
            run_layout.addLayout(arg_form)

            self.chk_bg = QCheckBox("Запустить в фоне (nohup ... > /tmp/exec_bg.log 2>&1 < /dev/null &)")
            self.chk_bg.setToolTip("Файл продолжит работу на ПК в фоновом режиме даже после отключения SSH")
            run_layout.addWidget(self.chk_bg)

            self.chk_gui = QCheckBox("Графическое приложение (GUI, DISPLAY=:0)")
            self.chk_gui.setToolTip("Полное отсоединение процесса с переменными DISPLAY и WAYLAND_DISPLAY")
            run_layout.addWidget(self.chk_gui)

            self.chk_terminal = QCheckBox("Запустить в графическом терминале (qterminal)")
            self.chk_terminal.setToolTip("Запуск в окне qterminal на рабочем столе пользователя с интерактивным bash")
            run_layout.addWidget(self.chk_terminal)

            layout.addWidget(run_group)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_submit = QPushButton("Запустить" if self.and_run else "Передать")
        self.btn_submit.setObjectName("btn_primary")
        self.btn_submit.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(self.btn_submit)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Выберите файл для передачи")
        if filename:
            self.edit_local.setText(filename)

    def _auto_update_remote_name(self, local_path: str):
        if local_path and not self.edit_remote.text():
            basename = os.path.basename(local_path)
            self.edit_remote.setText(f"/tmp/{basename}")

    def _validate_and_accept(self):
        local_path = self.edit_local.text().strip()
        remote_path = self.edit_remote.text().strip()

        if not local_path or not os.path.isfile(local_path):
            QMessageBox.warning(self, "Ошибка", "Укажите существующий локальный файл.")
            return

        if not remote_path:
            QMessageBox.warning(self, "Ошибка", "Укажите удаленный путь назначения.")
            return

        self.accept()

    def get_data(self) -> dict:
        return {
            "local_path": self.edit_local.text().strip(),
            "remote_path": self.edit_remote.text().strip(),
            "arguments": self.edit_args.text().strip() if self.and_run else "",
            "run_in_background": self.chk_bg.isChecked() if self.and_run else False,
            "is_gui_app": self.chk_gui.isChecked() if self.and_run else False,
            "in_terminal": self.chk_terminal.isChecked() if self.and_run else False,
        }


class RunExistingFileDialog(QDialog):
    """Диалог запуска уже существующего файла на удаленных ПК."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Запустить существующий файл на удаленных ПК")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.edit_path = QLineEdit()
        self.edit_path.setPlaceholderText("Например: /usr/local/bin/student_test.sh")
        form.addRow("Путь к файлу на ПК:", self.edit_path)

        self.edit_args = QLineEdit()
        self.edit_args.setPlaceholderText("Необязательные аргументы запуска")
        form.addRow("Аргументы:", self.edit_args)

        layout.addLayout(form)

        self.chk_bg = QCheckBox("Запустить в фоновом режиме (в фоне через nohup)")
        layout.addWidget(self.chk_bg)

        self.chk_gui = QCheckBox("Графическое приложение (GUI, DISPLAY=:0)")
        self.chk_gui.setToolTip("Полное отсоединение процесса с переменными DISPLAY и WAYLAND_DISPLAY")
        layout.addWidget(self.chk_gui)

        self.chk_terminal = QCheckBox("Запустить в графическом терминале (qterminal)")
        self.chk_terminal.setToolTip("Запуск в окне qterminal на рабочем столе пользователя с интерактивным bash")
        layout.addWidget(self.chk_terminal)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_submit = QPushButton("Запустить")
        self.btn_submit.setObjectName("btn_primary")
        self.btn_submit.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(self.btn_submit)

        layout.addLayout(btn_layout)

    def _validate_and_accept(self):
        if not self.edit_path.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите путь к исполняемому файлу.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "remote_path": self.edit_path.text().strip(),
            "arguments": self.edit_args.text().strip(),
            "run_in_background": self.chk_bg.isChecked(),
            "is_gui_app": self.chk_gui.isChecked(),
            "in_terminal": self.chk_terminal.isChecked(),
        }


class RunCommandDialog(QDialog):
    """Диалог ввода shell-команды с набором быстрых системных пресетов."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Выполнить произвольную shell-команду")
        self.setMinimumWidth(560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel("Введите bash/shell команду для запуска на всех выбранных машинах:")
        lbl.setStyleSheet("font-weight: 600; color: #8aadf4;")
        layout.addWidget(lbl)

        self.edit_cmd = QLineEdit()
        self.edit_cmd.setPlaceholderText("Например: systemctl restart networking или echo 'Hello' >> /tmp/test.txt")
        self.edit_cmd.setMinimumHeight(34)
        layout.addWidget(self.edit_cmd)

        # Быстрые пресеты
        preset_group = QGroupBox("Быстрые пресеты диагностики и управления")
        preset_layout = QVBoxLayout(preset_group)
        preset_row1 = QHBoxLayout()
        preset_row2 = QHBoxLayout()

        presets = [
            ("Место на диске", "df -h"),
            ("ОЗУ / Память", "free -h"),
            ("Аптайм", "uptime -p"),
            ("Пользователи", "who"),
            ("Сетевые адреса", "ip -brief address"),
            ("Ошибки служб", "systemctl --failed"),
        ]

        for i, (name, cmd) in enumerate(presets):
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, c=cmd: self.edit_cmd.setText(c))
            if i < 3:
                preset_row1.addWidget(btn)
            else:
                preset_row2.addWidget(btn)

        preset_layout.addLayout(preset_row1)
        preset_layout.addLayout(preset_row2)
        layout.addWidget(preset_group)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_exec = QPushButton("Выполнить команду")
        self.btn_exec.setObjectName("btn_primary")
        self.btn_exec.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(self.btn_exec)

        layout.addLayout(btn_layout)

    def _validate_and_accept(self):
        if not self.edit_cmd.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите команду для выполнения.")
            return
        self.accept()

    def get_command(self) -> str:
        return self.edit_cmd.text().strip()


class SaveProfileDialog(QDialog):
    """Диалог сохранения профиля кабинета."""

    def __init__(self, current_name: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Сохранить профиль кабинета")
        self.setFixedWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        self.edit_name = QLineEdit(current_name)
        self.edit_name.setPlaceholderText("Например: Кабинет 3 (Новый)")
        form.addRow("Название профиля:", self.edit_name)

        self.edit_desc = QLineEdit()
        self.edit_desc.setPlaceholderText("Краткое примечание (необязательно)")
        form.addRow("Описание:", self.edit_desc)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Сохранить")
        self.btn_save.setObjectName("btn_primary")
        self.btn_save.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _validate_and_accept(self):
        if not self.edit_name.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажите название профиля.")
            return
        self.accept()

    def get_data(self) -> Tuple[str, str]:
        return self.edit_name.text().strip(), self.edit_desc.text().strip()
