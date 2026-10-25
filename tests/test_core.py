"""
Модульные тесты для проверки бизнес-логики:
- Парсинг IP-адресов и диапазонов
- Генератор команд для целевых ОС
- Работа профилей кабинетов
"""

import os
import unittest
from config.settings import (
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

    def test_reboot_poweroff(self):
        reboot_cmd = OSCommandBuilder.get_reboot_command(use_sudo=True)
        self.assertIn("sudo -S", reboot_cmd)
        self.assertIn("reboot", reboot_cmd)

        poweroff_cmd = OSCommandBuilder.get_poweroff_command(use_sudo=False)
        self.assertEqual(poweroff_cmd, "poweroff")


class TestProfileManager(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
