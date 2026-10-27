"""
Конфигурация, константы и управление профилями кабинетов.
"""

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

# Поддерживаемые операционные системы
OS_ALT_LINUX = "Alt Linux"
OS_UBUNTU = "Ubuntu"
OS_DEBIAN = "Debian"
OS_ASTRA_LINUX = "Astra Linux"

SUPPORTED_OS = [
    OS_ALT_LINUX,
    OS_UBUNTU,
    OS_DEBIAN,
    OS_ASTRA_LINUX,
]

# Поддерживаемые архитектуры
ARCH_X86_64 = "x86_64 (amd64)"
ARCH_ARM = "ARM (aarch64)"
ARCH_ANY = "Автоопределение / Любая"

SUPPORTED_ARCH = [
    ARCH_X86_64,
    ARCH_ARM,
    ARCH_ANY,
]

DEFAULT_SSH_PORT = 22
DEFAULT_TIMEOUT_SEC = 15
DEFAULT_MAX_WORKERS = 20


def get_default_profiles_file() -> str:
    """Определяет путь к файлу профилей с учетом сред сборки (AppImage / PyInstaller)."""
    bundled_file = os.path.join(os.path.dirname(__file__), "profiles.json")
    if os.environ.get("APPIMAGE") or os.environ.get("APPDIR") or getattr(sys, "frozen", False):
        user_config_dir = os.path.join(os.path.expanduser("~"), ".config", "schooladm")
        os.makedirs(user_config_dir, exist_ok=True)
        user_file = os.path.join(user_config_dir, "profiles.json")
        if not os.path.exists(user_file) and os.path.exists(bundled_file):
            try:
                shutil.copyfile(bundled_file, user_file)
            except Exception:
                pass
        return user_file
    return bundled_file


PROFILES_FILE = get_default_profiles_file()


@dataclass
class ClassroomProfile:
    name: str
    ip_range_text: str
    username: str = "root"
    password: str = ""
    port: int = DEFAULT_SSH_PORT
    use_sudo: bool = False
    target_os: str = OS_ALT_LINUX
    target_arch: str = ARCH_X86_64
    description: str = ""
    use_individual_credentials: bool = False
    host_credentials: Dict[str, Dict[str, str]] = field(default_factory=dict)
    execution_mode: str = "parallel"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClassroomProfile":
        return cls(
            name=data.get("name", "Новый профиль"),
            ip_range_text=data.get("ip_range_text", ""),
            username=data.get("username", "root"),
            password=data.get("password", ""),
            port=data.get("port", DEFAULT_SSH_PORT),
            use_sudo=data.get("use_sudo", False),
            target_os=data.get("target_os", OS_ALT_LINUX),
            target_arch=data.get("target_arch", ARCH_X86_64),
            description=data.get("description", ""),
            use_individual_credentials=data.get("use_individual_credentials", False),
            host_credentials=data.get("host_credentials", {}),
            execution_mode=data.get("execution_mode", "parallel"),
        )


class ProfileManager:
    """Управляет сохранением и загрузкой профилей кабинетов в JSON-файл."""

    def __init__(self, filepath: str = PROFILES_FILE):
        self.filepath = filepath
        self._profiles: Dict[str, ClassroomProfile] = {}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.filepath):
            self._create_default_profiles()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._profiles = {
                    item["name"]: ClassroomProfile.from_dict(item)
                    for item in data.get("profiles", [])
                }
        except Exception:
            self._create_default_profiles()

    def save(self) -> None:
        data = {
            "version": 1,
            "profiles": [p.to_dict() for p in self._profiles.values()],
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all(self) -> List[ClassroomProfile]:
        return list(self._profiles.values())

    def get(self, name: str) -> Optional[ClassroomProfile]:
        return self._profiles.get(name)

    def set(self, profile: ClassroomProfile) -> None:
        self._profiles[profile.name] = profile
        self.save()

    def delete(self, name: str) -> bool:
        if name in self._profiles:
            del self._profiles[name]
            self.save()
            return True
        return False

    def _create_default_profiles(self) -> None:
        """Создает начальные шаблоны кабинетов для демонстрации."""
        p1 = ClassroomProfile(
            name="Кабинет информатики 1 (Альт Линукс)",
            ip_range_text="192.168.1.10-192.168.1.25",
            username="teacher",
            password="",
            port=22,
            use_sudo=True,
            target_os=OS_ALT_LINUX,
            target_arch=ARCH_X86_64,
            description="15 ПК учеников + учительский ПК на Альт Образование",
        )
        p2 = ClassroomProfile(
            name="Кабинет информатики 2 (Ubuntu/Debian)",
            ip_range_text="192.168.2.10-192.168.2.22",
            username="root",
            password="",
            port=22,
            use_sudo=False,
            target_os=OS_UBUNTU,
            target_arch=ARCH_X86_64,
            description="12 ПК учеников на Ubuntu Desktop",
        )
        p3 = ClassroomProfile(
            name="Мобильный класс (Astra Linux ARM)",
            ip_range_text="192.168.3.101-192.168.3.120",
            username="admin",
            password="",
            port=22,
            use_sudo=True,
            target_os=OS_ASTRA_LINUX,
            target_arch=ARCH_ARM,
            description="20 ноутбуков/планшетов на архитектуре ARM",
        )
        self._profiles = {p1.name: p1, p2.name: p2, p3.name: p3}
        self.save()
