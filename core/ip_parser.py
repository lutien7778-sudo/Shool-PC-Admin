"""
Модуль парсинга и валидации IP-адресов.
Поддерживает:
- Одиночные IP-адреса: 192.168.1.10
- Разделители: запятые, пробелы, переносы строк, точки с запятой
- Диапазоны полные: 192.168.1.10-192.168.1.25
- Диапазоны краткие: 192.168.1.10-25
- CIDR-подсети: 192.168.1.0/28
"""

import ipaddress
import re
from typing import List, Tuple


def parse_ip_targets(raw_text: str) -> Tuple[List[str], List[str]]:
    """
    Разбирает строку с IP-адресами, диапазонами и подсетями.
    
    Возвращает:
        (valid_ips, errors): список уникальных валидных IP в порядке добавления
                             и список сообщений о некорректных фрагментах.
    """
    if not raw_text or not raw_text.strip():
        return [], []

    # Разделяем по запятым, пробелам, точкам с запятой и переносам строк
    tokens = re.split(r'[\s,;]+', raw_text.strip())
    
    valid_ips: List[str] = []
    seen = set()
    errors: List[str] = []

    def add_ip(ip_str: str):
        if ip_str not in seen:
            seen.add(ip_str)
            valid_ips.append(ip_str)

    for token in tokens:
        if not token:
            continue

        # 1. Проверка на CIDR: 192.168.1.0/24
        if '/' in token:
            try:
                network = ipaddress.ip_network(token, strict=False)
                # Если сеть /31 или /32 - включаем все адреса, иначе исключаем network & broadcast
                hosts = list(network.hosts())
                if not hosts:
                    hosts = [network.network_address]
                for ip in hosts:
                    add_ip(str(ip))
            except ValueError:
                errors.append(f"Некорректная CIDR-подсеть: {token}")
            continue

        # 2. Проверка на диапазон: 192.168.1.10-192.168.1.25 или 192.168.1.10-25
        if '-' in token:
            parts = token.split('-', 1)
            start_str, end_str = parts[0].strip(), parts[1].strip()
            
            # Проверяем начальный адрес
            try:
                start_ip = ipaddress.IPv4Address(start_str)
            except ValueError:
                errors.append(f"Некорректное начало диапазона: {start_str}")
                continue

            # Конечный адрес может быть полным IP или просто числом последнего октета
            if '.' in end_str:
                try:
                    end_ip = ipaddress.IPv4Address(end_str)
                except ValueError:
                    errors.append(f"Некорректный конец диапазона: {end_str}")
                    continue
            else:
                # Краткая форма: 192.168.1.10-25 -> 192.168.1.25
                try:
                    last_octet = int(end_str)
                    if not (0 <= last_octet <= 255):
                        raise ValueError()
                    network_prefix = str(start_ip).rsplit('.', 1)[0]
                    end_ip = ipaddress.IPv4Address(f"{network_prefix}.{last_octet}")
                except ValueError:
                    errors.append(f"Некорректный октет конца диапазона: {end_str}")
                    continue

            # Проверяем, что start <= end
            start_int = int(start_ip)
            end_int = int(end_ip)
            if start_int > end_int:
                start_int, end_int = end_int, start_int

            # Ограничиваем максимальный размер диапазона для безопасности (макс. 1024 адреса)
            if end_int - start_int > 1024:
                errors.append(f"Диапазон слишком велик (макс 1024 адреса): {token}")
                continue

            for ip_int in range(start_int, end_int + 1):
                add_ip(str(ipaddress.IPv4Address(ip_int)))
            continue

        # 3. Одиночный IP
        try:
            ip = ipaddress.IPv4Address(token)
            add_ip(str(ip))
        except ValueError:
            errors.append(f"Некорректный IP-адрес: {token}")

    return valid_ips, errors
