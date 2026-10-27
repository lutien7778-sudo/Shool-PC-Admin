"""
Модульные тесты для проверки бизнес-логики:
- Парсинг IP-адресов и диапазонов
- Генератор команд для целевых ОС (включая GUI, qterminal, nohup, setsid и отсоединение дескрипторов)
- Работа профилей кабинетов с индивидуальными учетными данными и режимами выполнения
- Таймауты и обратная совместимость профилей
- Логика пула воркеров (параллельно / поочередно)
- Неблокирующий запуск фоновых задач в SSH-клиенте
"""

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

from config.settings import (
    DEFAULT_TIMEOUT_SEC,
    OS_ALT_LINUX,
    OS_ASTRA_LINUX,
    OS_DEBIAN,
    OS_UBUNTU,
    ClassroomProfile,
    ProfileManager,
)
from core.ip_parser import parse_ip_targets
from core.os_commands import OSCommandBuilder


class TestIPParser(unittest.TestCase):
    def test_single_ip(self):
        ips, errs = parse_ip_targets("192.168.1.10")
        self.assertEqual(ips, ["192.168.1.10"])
        self.assertEqual(errs, [])

    def test_delimiters(self):
        raw = "192.168.1.10, 192.168.1.11 \n 192.168.1.12; 192.168.1.13"
        ips, errs = parse_ip_targets(raw)
        self.assertEqual(ips, ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.13"])
        self.assertEqual(errs, [])

    def test_full_range(self):
        raw = "192.168.1.10-192.168.1.13"
        ips, errs = parse_ip_targets(raw)
        self.assertEqual(ips, ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.13"])
        self.assertEqual(errs, [])

    def test_short_range(self):
        raw = "10.0.0.5-8"
        ips, errs = parse_ip_targets(raw)
        self.assertEqual(ips, ["10.0.0.5", "10.0.0.6", "10.0.0.7", "10.0.0.8"])
        self.assertEqual(errs, [])

    def test_cidr(self):
        raw = "192.168.1.0/30"
        ips, errs = parse_ip_targets(raw)
        self.assertEqual(ips, ["192.168.1.1", "192.168.1.2"])
        self.assertEqual(errs, [])

    def test_deduplication(self):
        raw = "192.168.1.10, 192.168.1.10, 192.168.1.10-11"
        ips, errs = parse_ip_targets(raw)
        self.assertEqual(ips, ["192.168.1.10", "192.168.1.11"])
        self.assertEqual(errs, [])

    def test_invalid_tokens(self):
        raw = "192.168.1.300, invalid_ip, 192.168.1.5"
        ips, errs = parse_ip_targets(raw)
        self.assertEqual(ips, ["192.168.1.5"])
        self.assertEqual(len(errs), 2)


class TestOSCommands(unittest.TestCase):
    def test_alt_linux_update(self):
        cmd = OSCommandBuilder.get_update_command(OS_ALT_LINUX, use_sudo=False)
        self.assertIn("apt-get update", cmd)
        self.assertIn("dist-upgrade", cmd)

    def test_ubuntu_update_with_sudo(self):
        cmd = OSCommandBuilder.get_update_command(OS_UBUNTU, use_sudo=True)
        self.assertIn("sudo -S", cmd)
        self.assertIn("DEBIAN_FRONTEND=noninteractive", cmd)

    def test_run_file_background(self):
        cmd = OSCommandBuilder.get_run_file_command("/tmp/app.sh", "--flag", run_in_background=True, use_sudo=False)
        self.assertIn("nohup", cmd)
        self.assertIn("chmod +x", cmd)
        self.assertIn("&", cmd)
        self.assertIn("< /dev/null", cmd)

    def test_run_file_gui_detached(self):
        cmd = OSCommandBuilder.get_run_file_command(
            "/opt/app/my_gui",
            "--mode full",
            is_gui_app=True,
            use_sudo=False,
        )
        self.assertIn("DISPLAY=:0", cmd)
        self.assertIn("WAYLAND_DISPLAY=wayland-0", cmd)
        self.assertIn("XAUTHORITY=$HOME/.Xauthority", cmd)
        self.assertIn("nohup setsid", cmd)
        self.assertIn("< /dev/null", cmd)
        self.assertIn(">/dev/null 2>&1", cmd)
        self.assertIn("&", cmd)

    def test_run_file_gui_terminal_python(self):
        cmd = OSCommandBuilder.get_run_file_command(
            "/home/student/test.py",
            "",
            is_gui_app=True,
            in_terminal=True,
            use_sudo=False,
        )
        self.assertIn("DISPLAY=:0", cmd)
        self.assertIn("qterminal -e bash -c", cmd)
        self.assertIn("python3 '/home/student/test.py'", cmd)
        self.assertIn("exec bash", cmd)
        self.assertIn("< /dev/null", cmd)
        self.assertIn("&", cmd)

    def test_reboot_poweroff(self):
        reboot_cmd = OSCommandBuilder.get_reboot_command(use_sudo=True)
        self.assertIn("sudo -S", reboot_cmd)
        self.assertIn("reboot", reboot_cmd)

        poweroff_cmd = OSCommandBuilder.get_poweroff_command(use_sudo=False)
        self.assertEqual(poweroff_cmd, "poweroff")


class TestProfileManager(unittest.TestCase):
    def test_default_timeout(self):
        self.assertEqual(DEFAULT_TIMEOUT_SEC, 15)

    def test_profiles_crud(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_profiles.json")
        if os.path.exists(test_file):
            os.remove(test_file)

        mgr = ProfileManager(test_file)
        self.assertGreaterEqual(len(mgr.get_all()), 1)

        p = ClassroomProfile(
            name="Тестовый класс 99",
            ip_range_text="192.168.99.1-10",
            username="admin",
            use_sudo=True,
        )
        mgr.set(p)
        self.assertIsNotNone(mgr.get("Тестовый класс 99"))

        mgr.delete("Тестовый класс 99")
        self.assertIsNone(mgr.get("Тестовый класс 99"))

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_profile_individual_credentials_persistence(self):
        test_file = os.path.join(os.path.dirname(__file__), "test_profiles_creds.json")
        if os.path.exists(test_file):
            os.remove(test_file)

        mgr = ProfileManager(test_file)
        creds = {
            "192.168.1.10": {"username": "teacher", "password": "pass_teacher"},
            "192.168.1.11": {"username": "student1", "password": "pass_student1"},
        }
        p = ClassroomProfile(
            name="Класс с раздельными кредами",
            ip_range_text="192.168.1.10-11",
            username="default_user",
            password="default_pass",
            use_individual_credentials=True,
            host_credentials=creds,
            execution_mode="sequential",
        )
        mgr.set(p)

        # Перезагружаем менеджер с диска
        mgr2 = ProfileManager(test_file)
        loaded = mgr2.get("Класс с раздельными кредами")
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.use_individual_credentials)
        self.assertEqual(loaded.execution_mode, "sequential")
        self.assertEqual(loaded.host_credentials, creds)
        self.assertEqual(loaded.host_credentials["192.168.1.10"]["username"], "teacher")
        self.assertEqual(loaded.host_credentials["192.168.1.11"]["password"], "pass_student1")

        if os.path.exists(test_file):
            os.remove(test_file)

    def test_profile_backwards_compatibility(self):
        old_data = {
            "name": "Старый профиль",
            "ip_range_text": "10.0.0.1-5",
            "username": "root",
            "password": "old_pass",
            "port": 22,
        }
        p = ClassroomProfile.from_dict(old_data)
        self.assertFalse(p.use_individual_credentials)
        self.assertEqual(p.host_credentials, {})
        self.assertEqual(p.execution_mode, "parallel")


def _ensure_mocks():
    if "PyQt6" not in sys.modules or not hasattr(sys.modules.get("PyQt6", None), "QtWidgets"):
        m = types.ModuleType("PyQt6")
        mc = types.ModuleType("PyQt6.QtCore")
        mw = types.ModuleType("PyQt6.QtWidgets")
        mg = types.ModuleType("PyQt6.QtGui")

        class QtEnum:
            AlignCenter = 1
            Vertical = 1
            Horizontal = 2
            RichText = 1
            CustomContextMenu = 1
            class AlignmentFlag:
                AlignCenter = 1
            class Orientation:
                Vertical = 1
                Horizontal = 2
            class TextFormat:
                RichText = 1
            class ContextMenuPolicy:
                CustomContextMenu = 1

        mc.Qt = QtEnum

        class QThread:
            def __init__(self, *args, **kwargs): pass

        class QObject:
            def __init__(self, *args, **kwargs): pass

        def pyqtSignal(*types_args):
            class S:
                def emit(self, *a, **k): pass
                def connect(self, *a, **k): pass
            return S()

        mc.QThread = QThread
        mc.QObject = QObject
        mc.pyqtSignal = pyqtSignal

        class DummySignal:
            def connect(self, *a, **k): pass
            def emit(self, *a, **k): pass

        class DummyWidget:
            def __init__(self, *args, **kwargs):
                self._text = ""
                self._checked = False
                self._echo_mode = 0
                self.textChanged = DummySignal()
                self.clicked = DummySignal()
                self.itemClicked = DummySignal()
                self.customContextMenuRequested = DummySignal()
                self.itemSelectionChanged = DummySignal()
            def setText(self, t): self._text = str(t)
            def text(self): return self._text
            def setChecked(self, c): self._checked = bool(c)
            def isChecked(self): return self._checked
            def setEchoMode(self, m): self._echo_mode = m
            def echoMode(self): return self._echo_mode
            def setPlaceholderText(self, p): pass
            def setToolTip(self, t): pass
            def setFixedWidth(self, w): pass
            def setMinimumWidth(self, w): pass
            def setModal(self, m): pass
            def setWindowTitle(self, t): pass
            def setContentsMargins(self, *a): pass
            def setSpacing(self, *a): pass
            def addWidget(self, *a, **k): pass
            def addLayout(self, *a, **k): pass
            def addRow(self, *a, **k): pass
            def addStretch(self, *a): pass
            def __getattr__(self, name):
                return MagicMock()

        mw.QWidget = DummyWidget
        mw.QDialog = DummyWidget
        mw.QLineEdit = DummyWidget
        mw.QCheckBox = DummyWidget
        mw.QPushButton = DummyWidget
        mw.QLabel = DummyWidget
        mw.QGroupBox = DummyWidget
        mw.QFormLayout = DummyWidget
        mw.QVBoxLayout = DummyWidget
        mw.QHBoxLayout = DummyWidget
        mw.QFileDialog = MagicMock()
        mw.QMessageBox = MagicMock()
        mw.QTextEdit = DummyWidget
        mw.QTableWidget = DummyWidget
        mw.QTableWidgetItem = DummyWidget
        mw.QHeaderView = MagicMock()
        mw.QAbstractItemView = MagicMock()
        mw.QMenu = DummyWidget

        mg.QColor = lambda c: c
        mg.QIcon = lambda: None

        m.QtCore = mc
        m.QtWidgets = mw
        m.QtGui = mg
        sys.modules["PyQt6"] = m
        sys.modules["PyQt6.QtCore"] = mc
        sys.modules["PyQt6.QtWidgets"] = mw
        sys.modules["PyQt6.QtGui"] = mg

    if "paramiko" not in sys.modules:
        p_mock = types.ModuleType("paramiko")
        p_mock.SSHClient = MagicMock
        p_mock.AutoAddPolicy = MagicMock
        p_mock.AuthenticationException = type("AuthenticationException", (Exception,), {})
        p_mock.SSHException = type("SSHException", (Exception,), {})
        sys.modules["paramiko"] = p_mock


_ensure_mocks()
from core.task_runner import AsyncTaskThread
from core.ssh_client import SSHHostWorker
from ui.dialogs import FileTransferDialog, RunExistingFileDialog
from ui.host_table import HostTableWidget


class TestTaskRunnerLogic(unittest.TestCase):
    def test_pool_size_sequential(self):
        t = AsyncTaskThread(
            task_type="CHECK_AVAILABILITY",
            task_name="Тест",
            ips=["192.168.1.1", "192.168.1.2", "192.168.1.3"],
            port=22,
            username="root",
            password="",
            use_sudo=False,
            target_os=OS_ALT_LINUX,
            target_arch="x86_64",
            execution_mode="sequential",
        )
        self.assertEqual(t._calculate_pool_size(10), 1)

    def test_pool_size_parallel(self):
        t = AsyncTaskThread(
            task_type="CHECK_AVAILABILITY",
            task_name="Тест",
            ips=["192.168.1.1", "192.168.1.2"],
            port=22,
            username="root",
            password="",
            use_sudo=False,
            target_os=OS_ALT_LINUX,
            target_arch="x86_64",
            execution_mode="parallel",
        )
        # Для 2 хостов: пул равен 2
        self.assertEqual(t._calculate_pool_size(2), 2)
        # Для 10 хостов: пул ограничен 5
        self.assertEqual(t._calculate_pool_size(10), 5)

    def test_individual_credentials_selection(self):
        creds = {
            "192.168.1.10": {"username": "student10", "password": "pass10"},
        }
        t = AsyncTaskThread(
            task_type="CHECK_AVAILABILITY",
            task_name="Тест",
            ips=["192.168.1.10", "192.168.1.11"],
            port=22,
            username="common_user",
            password="common_password",
            use_sudo=False,
            target_os=OS_ALT_LINUX,
            target_arch="x86_64",
            host_credentials=creds,
        )

        # Проверяем учетные данные для хоста с индивидуальными кредами
        user_10 = t.username
        pass_10 = t.password
        if t.host_credentials and "192.168.1.10" in t.host_credentials:
            c = t.host_credentials["192.168.1.10"]
            user_10 = c.get("username", user_10)
            pass_10 = c.get("password", pass_10)
        self.assertEqual(user_10, "student10")
        self.assertEqual(pass_10, "pass10")

        # Проверяем учетные данные для хоста без индивидуальных кредов (фоллбэк)
        user_11 = t.username
        pass_11 = t.password
        if t.host_credentials and "192.168.1.11" in t.host_credentials:
            c = t.host_credentials["192.168.1.11"]
            user_11 = c.get("username", user_11)
            pass_11 = c.get("password", pass_11)
        self.assertEqual(user_11, "common_user")
        self.assertEqual(pass_11, "common_password")


class TestSSHClientDetachedExecution(unittest.TestCase):
    def test_non_blocking_gui_execution(self):
        worker = SSHHostWorker("192.168.1.10", username="root", password="123")
        
        # Создаем мок клиента и транспорта
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_channel = MagicMock()

        mock_client.get_transport.return_value = mock_transport
        mock_transport.open_session.return_value = mock_channel
        worker._client = mock_client

        exit_code, output = worker.execute_command_stream(
            "DISPLAY=:0 nohup setsid python3 /tmp/app.py >/dev/null 2>&1 < /dev/null &",
            wait_for_completion=False,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "Успешно запущен в фоне")
        mock_channel.close.assert_called_once()
        mock_client.close.assert_called_once()


class TestDialogsLogic(unittest.TestCase):
    def test_run_existing_file_dialog_data(self):
        dlg = RunExistingFileDialog()
        dlg.edit_path.setText("/usr/bin/my_script.py")
        dlg.edit_args.setText("--arg1 test")
        dlg.chk_bg.setChecked(True)
        dlg.chk_gui.setChecked(True)
        dlg.chk_terminal.setChecked(True)

        data = dlg.get_data()
        self.assertEqual(data["remote_path"], "/usr/bin/my_script.py")
        self.assertEqual(data["arguments"], "--arg1 test")
        self.assertTrue(data["run_in_background"])
        self.assertTrue(data["is_gui_app"])
        self.assertTrue(data["in_terminal"])

    def test_file_transfer_dialog_data_with_gui(self):
        dlg = FileTransferDialog(and_run=True)
        dlg.edit_local.setText("C:/local/test.py")
        dlg.edit_remote.setText("/tmp/test.py")
        dlg.edit_args.setText("-v")
        dlg.chk_gui.setChecked(True)
        dlg.chk_terminal.setChecked(False)

        data = dlg.get_data()
        self.assertEqual(data["local_path"], "C:/local/test.py")
        self.assertEqual(data["remote_path"], "/tmp/test.py")
        self.assertEqual(data["arguments"], "-v")
        self.assertTrue(data["is_gui_app"])
        self.assertFalse(data["in_terminal"])


class TestHostTableWidgetLogic(unittest.TestCase):
    def test_columns_structure(self):
        self.assertEqual(HostTableWidget.COL_IP, 0)
        self.assertEqual(HostTableWidget.COL_HOSTNAME, 1)
        self.assertEqual(HostTableWidget.COL_LOGIN, 2)
        self.assertEqual(HostTableWidget.COL_PASSWORD, 3)
        self.assertEqual(HostTableWidget.COL_OS_ARCH, 4)
        self.assertEqual(HostTableWidget.COL_STATUS, 5)
        self.assertEqual(HostTableWidget.COL_PING, 6)
        self.assertEqual(HostTableWidget.COL_DISK_UPTIME, 7)
        self.assertEqual(HostTableWidget.COL_DETAILS, 8)
        self.assertEqual(len(HostTableWidget.HEADERS), 9)

    def test_host_table_credentials_extraction(self):
        widget = HostTableWidget()
        mock_login = MagicMock()
        mock_login.text.return_value = "teacher_1"
        mock_pass = MagicMock()
        mock_pass.text.return_value = "secret_pass"

        widget._host_inputs["192.168.1.100"] = (mock_login, mock_pass)

        creds = widget.get_host_credentials()
        self.assertIn("192.168.1.100", creds)
        self.assertEqual(creds["192.168.1.100"]["username"], "teacher_1")
        self.assertEqual(creds["192.168.1.100"]["password"], "secret_pass")

        single = widget.get_credentials_for_host("192.168.1.100")
        self.assertIsNotNone(single)
        self.assertEqual(single["username"], "teacher_1")
        self.assertEqual(single["password"], "secret_pass")


if __name__ == "__main__":
    unittest.main()

