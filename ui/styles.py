"""
Стили оформления и CSS-тема для приложения SchoolAdm на PyQt6.
Современная темная тема с контрастной типографикой, аккуратными скруглениями
и четкими акцентными цветами для статусов.
"""

DARK_THEME_QSS = """
/* Главное окно и базовые виджеты */
QMainWindow, QDialog {
    background-color: #181926;
    color: #cad3f5;
    font-family: "Segoe UI", "Cantarell", "Ubuntu", sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: #181926;
    color: #cad3f5;
    font-size: 13px;
}

/* Группировочные блоки (QGroupBox) */
QGroupBox {
    background-color: #1e2030;
    border: 1px solid #363a4f;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #8aadf4;
    background-color: #1e2030;
    border-radius: 4px;
}

/* Поля ввода (QLineEdit, QTextEdit, QPlainTextEdit) */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #24273a;
    border: 1px solid #494d64;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cad3f5;
    selection-background-color: #8aadf4;
    selection-color: #181926;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #8aadf4;
    background-color: #2a2e46;
}

QLineEdit:disabled, QTextEdit:disabled {
    background-color: #181926;
    color: #6e738d;
    border-color: #363a4f;
}

/* Выпадающие списки (QComboBox) */
QComboBox {
    background-color: #24273a;
    border: 1px solid #494d64;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cad3f5;
    min-height: 22px;
}

QComboBox:hover {
    border: 1px solid #8aadf4;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #363a4f;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox QAbstractItemView {
    background-color: #1e2030;
    border: 1px solid #494d64;
    border-radius: 6px;
    selection-background-color: #363a4f;
    selection-color: #8aadf4;
    color: #cad3f5;
    padding: 4px;
}

/* Кнопки (QPushButton) */
QPushButton {
    background-color: #363a4f;
    border: 1px solid #494d64;
    border-radius: 6px;
    color: #cad3f5;
    padding: 7px 14px;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #494d64;
    border-color: #8aadf4;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #24273a;
    border-color: #7dc4e4;
}

QPushButton:disabled {
    background-color: #1e2030;
    color: #5b6078;
    border-color: #2b2e42;
}

/* Акцентные кнопки */
QPushButton#btn_primary {
    background-color: #26547c;
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#btn_primary:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

QPushButton#btn_success {
    background-color: #1e463a;
    border: 1px solid #22c55e;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#btn_success:hover {
    background-color: #15803d;
    border-color: #4ade80;
}

QPushButton#btn_danger {
    background-color: #4a1f28;
    border: 1px solid #f43f5e;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#btn_danger:hover {
    background-color: #9f1239;
    border-color: #fb7185;
}

QPushButton#btn_warning {
    background-color: #4d3a17;
    border: 1px solid #f59e0b;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#btn_warning:hover {
    background-color: #b45309;
    border-color: #fbbf24;
}

/* Таблица хостов (QTableWidget) */
QTableWidget {
    background-color: #1e2030;
    border: 1px solid #363a4f;
    border-radius: 8px;
    gridline-color: #282a3d;
    selection-background-color: #363a4f;
    selection-color: #ffffff;
    color: #cad3f5;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #282a3d;
}

QTableWidget::item:selected {
    background-color: #2f344d;
    color: #8aadf4;
}

QHeaderView::section {
    background-color: #24273a;
    color: #a5adcb;
    font-weight: 600;
    border: none;
    border-bottom: 2px solid #363a4f;
    padding: 8px;
}

/* Радиокнопки и чекбоксы */
QRadioButton, QCheckBox {
    spacing: 8px;
    color: #cad3f5;
}

QRadioButton::indicator, QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #494d64;
    background-color: #24273a;
}

QRadioButton::indicator:checked, QCheckBox::indicator:checked {
    background-color: #8aadf4;
    border-color: #8aadf4;
}

QRadioButton::indicator {
    border-radius: 8px;
}

/* Скроллбары */
QScrollBar:vertical {
    background-color: #181926;
    width: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #363a4f;
    min-height: 24px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #494d64;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #181926;
    height: 10px;
    margin: 0;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #363a4f;
    min-width: 24px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #494d64;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Прогресс-бар */
QProgressBar {
    background-color: #24273a;
    border: 1px solid #363a4f;
    border-radius: 6px;
    height: 14px;
    text-align: center;
    color: #ffffff;
    font-size: 11px;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #8aadf4;
    border-radius: 5px;
}

/* Разделители (QSplitter) */
QSplitter::handle {
    background-color: #282a3d;
}

QSplitter::handle:hover {
    background-color: #8aadf4;
}

/* Консоль логов */
QPlainTextEdit#log_console {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 8px;
    color: #a6adc8;
    font-family: "Consolas", "Cascadia Code", "DejaVu Sans Mono", "Monospace";
    font-size: 12px;
    line-height: 1.4;
}

/* Всплывающие подсказки */
QToolTip {
    background-color: #24273a;
    color: #cad3f5;
    border: 1px solid #494d64;
    border-radius: 4px;
    padding: 4px 8px;
}

/* Статус-бар */
QStatusBar {
    background-color: #181926;
    border-top: 1px solid #282a3d;
    color: #a5adcb;
    font-size: 12px;
}
"""


def get_status_badge_html(status: str) -> str:
    """Возвращает форматированный HTML-бейдж статуса с цветовой подсветкой."""
    status_colors = {
        "Успешно": ("#1e463a", "#4ade80"),     # фон, текст
        "В процессе": ("#1c3a5e", "#60a5fa"),
        "Ошибка": ("#4a1f28", "#fb7185"),
        "Ожидание": ("#2e3146", "#a5adcb"),
    }
    bg, fg = status_colors.get(status, ("#2e3146", "#a5adcb"))
    return (
        f'<span style="background-color: {bg}; color: {fg}; '
        f'padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">'
        f'{status}</span>'
    )
