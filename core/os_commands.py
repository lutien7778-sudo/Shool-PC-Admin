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
        is_gui_app: bool = False,
        use_sudo: bool = False,
        in_terminal: bool = False,
    ) -> str:
        """
        Команда выставления прав на исполнение (chmod +x) и запуска файла.

        Параметры:
            remote_path: Путь к файлу на удаленном хосте
            arguments: Аргументы командной строки
            run_in_background: Если True, запускает в фоне через nohup с отсоединением дескрипторов
            is_gui_app: Если True, использует setsid/nohup с переменными окружения для GUI
            use_sudo: Если True, оборачивает в sudo
            in_terminal: Если True, запускает внутри GUI-терминала qterminal
        """
        args_str = f" {arguments.strip()}" if arguments.strip() else ""
        is_py = remote_path.endswith(".py")
        exec_target = f"python3 '{remote_path}'{args_str}" if is_py else f"'{remote_path}'{args_str}"
        chmod_cmd = f"chmod +x '{remote_path}'"

        gui_env = "DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XAUTHORITY=$HOME/.Xauthority"

        if in_terminal:
            # Запуск в графическом терминале qterminal с сохранением сессии bash
            inner_cmd = f"{exec_target}; exec bash"
            safe_inner = inner_cmd.replace('"', '\\"')
            cmd = (
                f"{chmod_cmd} && "
                f"{gui_env} nohup qterminal -e bash -c \"{safe_inner}\" "
                f">/dev/null 2>&1 < /dev/null &"
            )
        elif is_gui_app:
            # Для GUI-приложений: полное отсоединение через setsid с переменными окружения
            cmd = (
                f"{chmod_cmd} && "
                f"{gui_env} nohup setsid {exec_target} "
                f">/dev/null 2>&1 < /dev/null &"
            )
        elif run_in_background:
            # Запуск в фоне через nohup с полным отсоединением всех дескрипторов
            cmd = f"{chmod_cmd} && nohup {exec_target} > /tmp/exec_bg.log 2>&1 < /dev/null &"
        else:
            cmd = f"{chmod_cmd} && {exec_target}"

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
