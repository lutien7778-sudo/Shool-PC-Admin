"""
Генератор системных команд для целевых дистрибутивов Linux
(Альт Линукс, Ubuntu, Debian, Astra Linux) и архитектур.
"""

from typing import Optional
from config.settings import (
    OS_ALT_LINUX,
    OS_UBUNTU,
    OS_DEBIAN,
    OS_ASTRA_LINUX,
)


class OSCommandBuilder:
    """Формирует команды с учетом дистрибутива, архитектуры и прав (root/sudo)."""

    @staticmethod
    def wrap_sudo(command: str, use_sudo: bool) -> str:
        """
        Если требуется sudo, оборачивает команду в sudo -S -p '' bash -c '...'
        для неинтерактивного ввода пароля через stdin.
        """
        if not use_sudo:
            return command
        # Экранируем одинарные кавычки в теле команды
        safe_cmd = command.replace("'", "'\"'\"'")
        return f"sudo -S -p '' bash -c '{safe_cmd}'"

    @classmethod
    def get_update_command(cls, os_name: str, use_sudo: bool = False) -> str:
        """
        Возвращает команду обновления пакетной базы и системы для выбранной ОС.
        """
        if os_name == OS_ALT_LINUX:
            # Для Alt Linux: обновление пакетного репозитория и dist-upgrade
            cmd = "apt-get update && apt-get dist-upgrade -y"
        else:
            # Для Ubuntu, Debian, Astra Linux:
            # Флаг DEBIAN_FRONTEND=noninteractive предотвращает зависание на запросах debconf
            cmd = "export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get upgrade -y"
        return cls.wrap_sudo(cmd, use_sudo)

    @classmethod
    def get_reboot_command(cls, use_sudo: bool = False) -> str:
        """Команда немедленной перезагрузки."""
        cmd = "reboot"
        return cls.wrap_sudo(cmd, use_sudo)

    @classmethod
    def get_poweroff_command(cls, use_sudo: bool = False) -> str:
        """Команда немедленного выключения."""
        cmd = "poweroff"
        return cls.wrap_sudo(cmd, use_sudo)

    @classmethod
    def get_run_file_command(
        cls,
        remote_path: str,
        arguments: str = "",
        run_in_background: bool = False,
        use_sudo: bool = False,
    ) -> str:
        """
        Команда выставления прав на исполнение (chmod +x) и запуска файла.
        """
        args_str = f" {arguments.strip()}" if arguments.strip() else ""
        if run_in_background:
            # Запуск в фоне через nohup с перенаправлением вывода в лог-файл
            cmd = f"chmod +x '{remote_path}' && nohup '{remote_path}'{args_str} > /tmp/exec_bg.log 2>&1 &"
        else:
            cmd = f"chmod +x '{remote_path}' && '{remote_path}'{args_str}"
        return cls.wrap_sudo(cmd, use_sudo)

    @classmethod
    def get_system_info_command(cls) -> str:
        """
        Легковесный скрипт для сбора базовой информации о машине:
        - Имя хоста
        - Название ОС из /etc/os-release
        - Архитектура процессора (uname -m)
        - Свободное место на диске /
        - Время работы (uptime)
        Формат вывода: HOSTNAME|OS_PRETTY|ARCH|DISK_AVAIL|UPTIME
        """
        script = (
            "H=$(hostname 2>/dev/null || uname -n); "
            "if [ -f /etc/os-release ]; then . /etc/os-release; OS=\"$PRETTY_NAME\"; else OS=$(uname -s); fi; "
            "ARCH=$(uname -m 2>/dev/null || echo 'unknown'); "
            "DISK=$(df -h / 2>/dev/null | awk 'NR==2 {print $4}' || echo 'N/A'); "
            "UP=$(uptime -p 2>/dev/null || uptime 2>/dev/null | awk -F'( |,|:)+' '{print $6,\"hrs\"}' || echo 'N/A'); "
            "echo \"$H|$OS|$ARCH|$DISK|$UP\""
        )
        return script
