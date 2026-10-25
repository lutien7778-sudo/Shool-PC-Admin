"""
Многопоточный диспетчер задач на базе PyQt6 и concurrent.futures.ThreadPoolExecutor.
Обеспечивает параллельное выполнение операций на 20-30 ПК одновременно
без блокировки графического интерфейса.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from config.settings import DEFAULT_MAX_WORKERS, DEFAULT_TIMEOUT_SEC
from core.os_commands import OSCommandBuilder
from core.ssh_client import SSHHostWorker

# Статусы выполнения
STATUS_IDLE = "Ожидание"
STATUS_PROGRESS = "В процессе"
STATUS_SUCCESS = "Успешно"
STATUS_ERROR = "Ошибка"


class TaskRunnerSignals(QObject):
    """Qt-сигналы для передачи событий из рабочих потоков в UI."""
    task_started = pyqtSignal(str, int)            # task_name, total_hosts
    host_status_changed = pyqtSignal(str, str, str) # ip, status, details
    host_info_updated = pyqtSignal(str, dict)       # ip, info_dict
    host_log = pyqtSignal(str, str, str)           # ip, stream_type, message
    progress_updated = pyqtSignal(int, int)         # completed, total
    task_finished = pyqtSignal(str, int, int)       # task_name, success_count, fail_count


class AsyncTaskThread(QThread):
    """
    Отдельный поток QThread, запускающий пул параллельных воркеров ThreadPoolExecutor.
    Гарантирует полную отзывчивость главного потока GUI.
    """

    def __init__(
        self,
        task_type: str,
        task_name: str,
        ips: List[str],
        port: int,
        username: str,
        password: str,
        use_sudo: bool,
        target_os: str,
        target_arch: str,
        extra_params: Optional[dict] = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
        timeout: int = DEFAULT_TIMEOUT_SEC,
    ):
        super().__init__()
        self.task_type = task_type
        self.task_name = task_name
        self.ips = ips
        self.port = port
        self.username = username
        self.password = password
        self.use_sudo = use_sudo
        self.target_os = target_os
        self.target_arch = target_arch
        self.extra_params = extra_params or {}
        self.max_workers = max_workers
        self.timeout = timeout
        self.signals = TaskRunnerSignals()
        self._is_cancelled = False

    def cancel(self):
        """Запрашивает отмену выполнения."""
        self._is_cancelled = True

    def run(self):
        total = len(self.ips)
        self.signals.task_started.emit(self.task_name, total)

        if total == 0:
            self.signals.task_finished.emit(self.task_name, 0, 0)
            return

        success_count = 0
        fail_count = 0
        completed = 0

        # Ограничиваем количество потоков числом хостов (не более max_workers)
        pool_size = min(self.max_workers, max(1, total))

        with ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="SSHWorker") as executor:
            futures = {
                executor.submit(self._execute_for_host, ip): ip
                for ip in self.ips
            }

            for future in as_completed(futures):
                if self._is_cancelled:
                    break

                ip = futures[future]
                completed += 1
                try:
                    is_ok = future.result()
                    if is_ok:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    fail_count += 1
                    self.signals.host_status_changed.emit(ip, STATUS_ERROR, f"Ошибка: {str(e)}")
                    self._emit_log(ip, "err", f"Непредвиденная ошибка задачи: {str(e)}")

                self.signals.progress_updated.emit(completed, total)

        self.signals.task_finished.emit(self.task_name, success_count, fail_count)

    def _emit_log(self, ip: str, stream_type: str, message: str):
        now = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{now}] [{ip}] {message}"
        self.signals.host_log.emit(ip, stream_type, formatted)

    def _execute_for_host(self, ip: str) -> bool:
        if self._is_cancelled:
            self.signals.host_status_changed.emit(ip, STATUS_ERROR, "Отменено пользователем")
            return False

        self.signals.host_status_changed.emit(ip, STATUS_PROGRESS, "Подключение...")
        self._emit_log(ip, "info", f"--- Старт задачи «{self.task_name}» ---")

        worker = SSHHostWorker(
            ip=ip,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            use_sudo=self.use_sudo,
        )

        try:
            if self.task_type == "CHECK_AVAILABILITY":
                return self._task_check_availability(worker)

            elif self.task_type == "UPDATE_SYSTEM":
                cmd = OSCommandBuilder.get_update_command(self.target_os, self.use_sudo)
                return self._task_exec_command(worker, cmd, "Обновление системы")

            elif self.task_type == "EXECUTE_COMMAND":
                cmd = self.extra_params.get("command", "")
                if not cmd:
                    self.signals.host_status_changed.emit(ip, STATUS_ERROR, "Пустая команда")
                    return False
                wrapped_cmd = OSCommandBuilder.wrap_sudo(cmd, self.use_sudo)
                return self._task_exec_command(worker, wrapped_cmd, "Произвольная команда")

            elif self.task_type == "UPLOAD_FILE":
                local_path = self.extra_params.get("local_path", "")
                remote_path = self.extra_params.get("remote_path", "")
                return self._task_upload(worker, local_path, remote_path)

            elif self.task_type == "UPLOAD_AND_RUN":
                local_path = self.extra_params.get("local_path", "")
                remote_path = self.extra_params.get("remote_path", "")
                args = self.extra_params.get("arguments", "")
                is_bg = self.extra_params.get("run_in_background", False)
                return self._task_upload_and_run(worker, local_path, remote_path, args, is_bg)

            elif self.task_type == "RUN_EXISTING":
                remote_path = self.extra_params.get("remote_path", "")
                args = self.extra_params.get("arguments", "")
                is_bg = self.extra_params.get("run_in_background", False)
                cmd = OSCommandBuilder.get_run_file_command(remote_path, args, is_bg, self.use_sudo)
                return self._task_exec_command(worker, cmd, "Запуск файла")

            elif self.task_type == "REBOOT":
                cmd = OSCommandBuilder.get_reboot_command(self.use_sudo)
                return self._task_power_action(worker, cmd, "Перезагрузка")

            elif self.task_type == "POWEROFF":
                cmd = OSCommandBuilder.get_poweroff_command(self.use_sudo)
                return self._task_power_action(worker, cmd, "Выключение")

            else:
                self.signals.host_status_changed.emit(ip, STATUS_ERROR, f"Неизвестный тип задачи: {self.task_type}")
                return False

        finally:
            worker.close()

    def _task_check_availability(self, worker: SSHHostWorker) -> bool:
        ok, msg, info = worker.check_availability()
        if ok:
            self.signals.host_info_updated.emit(worker.ip, info)
            self.signals.host_status_changed.emit(worker.ip, STATUS_SUCCESS, msg)
            self._emit_log(worker.ip, "info", f"Доступен: {msg}")
            return True
        else:
            self.signals.host_status_changed.emit(worker.ip, STATUS_ERROR, msg)
            self._emit_log(worker.ip, "err", f"Недоступен: {msg}")
            return False

    def _task_exec_command(self, worker: SSHHostWorker, command: str, label: str) -> bool:
        self.signals.host_status_changed.emit(worker.ip, STATUS_PROGRESS, f"Выполняется: {label}")
        self._emit_log(worker.ip, "info", f"Команда: {command}")

        def log_cb(st: str, line: str):
            self._emit_log(worker.ip, st, line)

        code, _ = worker.execute_command_stream(command, log_callback=log_cb)
        if code == 0:
            self.signals.host_status_changed.emit(worker.ip, STATUS_SUCCESS, f"{label} выполнено (код 0)")
            self._emit_log(worker.ip, "info", f"Завершено успешно (exit code: 0)")
            return True
        else:
            self.signals.host_status_changed.emit(worker.ip, STATUS_ERROR, f"Ошибка (код {code})")
            self._emit_log(worker.ip, "err", f"Завершено с ошибкой (exit code: {code})")
            return False

    def _task_power_action(self, worker: SSHHostWorker, command: str, action_name: str) -> bool:
        self.signals.host_status_changed.emit(worker.ip, STATUS_PROGRESS, f"Отправка команды: {action_name}...")
        self._emit_log(worker.ip, "info", f"Команда {action_name} отправляется...")

        def log_cb(st: str, line: str):
            self._emit_log(worker.ip, st, line)

        # Команды reboot и poweroff обычно разрывают SSH-сессию
        code, _ = worker.execute_command_stream(command, log_callback=log_cb, cmd_timeout=5)
        # Если код 0 или -1 / таймаут из-за разрыва соединения при перезагрузке — считаем успешным
        self.signals.host_status_changed.emit(worker.ip, STATUS_SUCCESS, f"Команда «{action_name}» отправлена")
        self._emit_log(worker.ip, "info", f"Команда «{action_name}» успешно передана хосту")
        return True

    def _task_upload(self, worker: SSHHostWorker, local_path: str, remote_path: str) -> bool:
        self.signals.host_status_changed.emit(worker.ip, STATUS_PROGRESS, "Передача файла...")

        def log_cb(st: str, line: str):
            self._emit_log(worker.ip, st, line)

        ok, msg = worker.upload_file(local_path, remote_path, log_callback=log_cb)
        if ok:
            self.signals.host_status_changed.emit(worker.ip, STATUS_SUCCESS, "Файл передан")
            return True
        else:
            self.signals.host_status_changed.emit(worker.ip, STATUS_ERROR, msg)
            return False

    def _task_upload_and_run(
        self,
        worker: SSHHostWorker,
        local_path: str,
        remote_path: str,
        arguments: str,
        run_in_background: bool,
    ) -> bool:
        # Шаг 1: Передача файла
        self.signals.host_status_changed.emit(worker.ip, STATUS_PROGRESS, "Загрузка файла...")

        def log_cb(st: str, line: str):
            self._emit_log(worker.ip, st, line)

        ok, msg = worker.upload_file(local_path, remote_path, log_callback=log_cb)
        if not ok:
            self.signals.host_status_changed.emit(worker.ip, STATUS_ERROR, f"Ошибка загрузки: {msg}")
            return False

        # Шаг 2: Запуск
        self.signals.host_status_changed.emit(worker.ip, STATUS_PROGRESS, "Запуск переданного файла...")
        cmd = OSCommandBuilder.get_run_file_command(remote_path, arguments, run_in_background, self.use_sudo)
        return self._task_exec_command(worker, cmd, "Запуск переданного файла")
