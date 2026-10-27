"""
Модуль сетевого взаимодействия по SSH и SFTP на базе Paramiko.
Обеспечивает:
- Проверку доступности машин
- Сбор системной информации (хост, ОС, архитектура, диск, uptime)
- Потоковое выполнение команд с поддержкой sudo и real-time логов
- Передачу файлов по SFTP с контролем прогресса
- Корректную обработку сетевых ошибок и таймаутов
"""

import os
import posixpath
import socket
import time
from typing import Callable, Optional, Tuple

import paramiko
from core.os_commands import OSCommandBuilder


class SSHHostWorker:
    """Управляет SSH-сессией и SFTP-операциями для одного целевого хоста."""

    def __init__(
        self,
        ip: str,
        port: int = 22,
        username: str = "root",
        password: str = "",
        timeout: int = 15,  # Увеличен с 6 до 15 секунд
        use_sudo: bool = False,
    ):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.use_sudo = use_sudo
        self._client: Optional[paramiko.SSHClient] = None

    def _create_client(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    def connect(self) -> paramiko.SSHClient:
        """Устанавливает SSH-соединение с заданными таймаутами."""
        if self._client is not None:
            try:
                transport = self._client.get_transport()
                if transport and transport.is_active():
                    return self._client
            except Exception:
                pass

        client = self._create_client()
        client.connect(
            hostname=self.ip,
            port=self.port,
            username=self.username,
            password=self.password if self.password else None,
            timeout=self.timeout,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        self._client = client
        return client

    def close(self) -> None:
        """Закрывает активное соединение."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def check_availability(self) -> Tuple[bool, str, dict]:
        """
        Проверяет доступность хоста (SSH + базовый инфо-запрос).
        Возвращает:
            (is_online, message, info_dict)
            info_dict содержит: hostname, os, arch, disk, uptime
        """
        info = {
            "hostname": "",
            "os": "Неизвестно",
            "arch": "Неизвестно",
            "disk": "N/A",
            "uptime": "N/A",
        }

        # 1. Быстрая проверка TCP-порта перед полным SSH-хэндшейком
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(min(15.0, float(self.timeout)))
        try:
            res = sock.connect_ex((self.ip, self.port))
            if res != 0:
                sock.close()
                return False, f"Порт {self.port} недоступен (хост выключен или брандмауэр)", info
            sock.close()
        except socket.timeout:
            sock.close()
            return False, "Таймаут подключения к порту (хост выключен)", info
        except Exception as e:
            sock.close()
            return False, f"Сетевая ошибка: {str(e)}", info

        # 2. Подключение по SSH
        try:
            client = self.connect()
            # 3. Выполняем быстрый опрос характеристик системы
            probe_cmd = OSCommandBuilder.get_system_info_command()
            stdin, stdout, stderr = client.exec_command(probe_cmd, timeout=self.timeout)
            out_str = stdout.read().decode("utf-8", errors="replace").strip()

            if out_str and "|" in out_str:
                parts = out_str.split("|")
                if len(parts) >= 5:
                    info["hostname"] = parts[0]
                    info["os"] = parts[1]
                    info["arch"] = parts[2]
                    info["disk"] = parts[3]
                    info["uptime"] = parts[4]

            msg = f"Онлайн ({info['os']}, {info['arch']}, Диск: {info['disk']})"
            return True, msg, info

        except paramiko.AuthenticationException:
            return False, "Ошибка аутентификации (неверный логин или пароль)", info
        except socket.timeout:
            return False, "Таймаут SSH-соединения", info
        except paramiko.SSHException as e:
            return False, f"Ошибка SSH-протокола: {str(e)}", info
        except Exception as e:
            return False, f"Ошибка подключения: {str(e)}", info
        finally:
            self.close()

    def execute_command_stream(
        self,
        command: str,
        log_callback: Optional[Callable[[str, str], None]] = None,
        cmd_timeout: Optional[int] = None,
        wait_for_completion: bool = True,
    ) -> Tuple[int, str]:
        """
        Выполняет shell-команду на удаленном хосте с потоковым выводом stdout/stderr.

        Параметры:
            command: Команда для выполнения (при use_sudo предварительно оборачивается)
            log_callback: Функция log_callback(stream_type, line), stream_type in ('out', 'err', 'info')
            cmd_timeout: Таймаут выполнения в секундах (None = без ограничений)
            wait_for_completion: Если False, не ждет завершения команды (для фоновых GUI-задач)

        Возвращает:
            (exit_code, full_output)
        """
        def emit(stream_type: str, text: str):
            if log_callback:
                log_callback(stream_type, text)

        try:
            client = self.connect()
        except paramiko.AuthenticationException:
            err = "Ошибка: Неверный логин или пароль."
            emit("err", err)
            return -1, err
        except Exception as e:
            err = f"Ошибка подключения к {self.ip}:{self.port} — {str(e)}"
            emit("err", err)
            return -1, err

        full_output = []
        try:
            # Используем PTY для корректной работы sudo и цветного/построчного вывода
            transport = client.get_transport()
            if not transport:
                emit("err", "Не удалось получить SSH Transport.")
                return -1, "No transport"

            channel = transport.open_session()
            channel.get_pty()
            channel.settimeout(cmd_timeout)
            channel.exec_command(command)

            # Если команда запущена через sudo, передаем пароль на запрос sudo
            if self.use_sudo and self.password:
                # Отправляем пароль при старте для sudo -S
                channel.send(self.password + "\n")

            # Если не ждем завершения (фоновые GUI-задачи), сразу фиксируем статус и закрываем канал
            if not wait_for_completion:
                time.sleep(0.3)
                emit("info", "Команда отправлена на выполнение (фоновый режим)")
                try:
                    channel.close()
                except Exception:
                    pass
                return 0, "Успешно запущен в фоне"

            # Читаем вывод из канала в реальном времени
            buffer = ""
            while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
                if channel.recv_ready():
                    data = channel.recv(4096).decode("utf-8", errors="replace")
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        # Фильтруем эхо пароля если оно возникло
                        clean_line = line.rstrip("\r")
                        if self.password and clean_line.strip() == self.password.strip():
                            continue
                        full_output.append(clean_line)
                        emit("out", clean_line)

                if channel.recv_stderr_ready():
                    err_data = channel.recv_stderr(4096).decode("utf-8", errors="replace")
                    for err_line in err_data.splitlines():
                        full_output.append(err_line)
                        emit("err", err_line)

                # Небольшая пауза для разгрузки процессора
                time.sleep(0.05)

            # Дочитываем оставшийся буфер
            if buffer.strip():
                clean_line = buffer.rstrip("\r\n")
                if not (self.password and clean_line.strip() == self.password.strip()):
                    full_output.append(clean_line)
                    emit("out", clean_line)

            exit_status = channel.recv_exit_status()
            channel.close()
            return exit_status, "\n".join(full_output)

        except socket.timeout:
            err = f"Превышен таймаут выполнения команды ({cmd_timeout} сек)."
            emit("err", err)
            return -2, err
        except Exception as e:
            err = f"Исключение при выполнении команды: {str(e)}"
            emit("err", err)
            return -3, err
        finally:
            self.close()

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Передает локальный файл на удаленный хост через SFTP с индикацией прогресса.
        
        Возвращает:
            (success, message)
        """
        def emit(stream_type: str, text: str):
            if log_callback:
                log_callback(stream_type, text)

        if not os.path.isfile(local_path):
            err = f"Локальный файл не найден: {local_path}"
            emit("err", err)
            return False, err

        file_size = os.path.getsize(local_path)
        emit("info", f"Подготовка к передаче: {os.path.basename(local_path)} ({file_size} байт) -> {remote_path}")

        try:
            client = self.connect()
            sftp = client.open_sftp()
        except Exception as e:
            err = f"Не удалось открыть SFTP-сессию: {str(e)}"
            emit("err", err)
            return False, err

        try:
            # Проверяем и создаем удаленную директорию при необходимости
            remote_dir = posixpath.dirname(remote_path)
            if remote_dir and remote_dir not in (".", "/"):
                self._ensure_remote_dir(sftp, remote_dir)

            # Колбэк прогресса с защитой от слишком частого вызова
            last_percent = [-1]

            def sftp_cb(transferred: int, total: int):
                pct = int((transferred / total) * 100) if total > 0 else 0
                if pct != last_percent[0]:
                    last_percent[0] = pct
                    if progress_callback:
                        progress_callback(transferred, total)
                    if pct % 25 == 0:
                        emit("info", f"Загрузка: {pct}% ({transferred}/{total} байт)")

            sftp.put(local_path, remote_path, callback=sftp_cb)
            sftp.close()
            msg = f"Файл успешно передан в {remote_path}"
            emit("info", msg)
            return True, msg

        except IOError as e:
            err = f"Ошибка ввода-вывода SFTP (нехватка места / права доступа): {str(e)}"
            emit("err", err)
            return False, err
        except Exception as e:
            err = f"Ошибка передачи SFTP: {str(e)}"
            emit("err", err)
            return False, err
        finally:
            self.close()

    def _ensure_remote_dir(self, sftp, remote_directory: str) -> None:
        """Рекурсивно создает директорию на удаленном хосте при отсутствии."""
        dirs = []
        head = remote_directory
        while len(head) > 1:
            head, tail = posixpath.split(head)
            if tail:
                dirs.append(tail)
            if head == "/":
                break
        dirs.reverse()

        current = ""
        for part in dirs:
            current = posixpath.join(current, part) if current else f"/{part}"
            try:
                sftp.stat(current)
            except IOError:
                try:
                    sftp.mkdir(current)
                except Exception:
                    pass
