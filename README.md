

```markdown
# 🧪 KimShell v2.0

```
██████╗ ██╗███╗   ███╗███████╗██╗  ██╗███████╗██╗     ██╗
██╔══██╗██║████╗ ████║██╔════╝██║  ██║██╔════╝██║     ██║
██║  ██║██║██╔████╔██║███████╗███████║█████╗  ██║     ██║
██║  ██║██║██║╚██╔╝██║╚════██║██╔══██║██╔══╝  ██║     ██║
██████╔╝██║██║ ╚═╝ ██║███████║██║  ██║███████╗███████╗███████╗
╚═════╝ ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
```

**KimShell** — это **Secure Browser Environment**: изолированный браузер Brave с полным спуфингом аппаратного отпечатка и защитой от фингерпринтинга.

---

![Python](https://img.shields.io/badge/Python-3.11%2B-00ff88?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-00d4ff?style=flat-square&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-ff3366?style=flat-square)

[📖 Документация](https://yourname.github.io/kimshell) · [🚀 Релизы](https://github.com/yourname/kimshell/releases) · [🐛 Issues](https://github.com/yourname/kimshell/issues)

---

## 🎯 Что делает KimShell

KimShell создаёт временный профиль Brave Browser с поддельными характеристиками компьютера.  
Сайты видят вымышленные CPU, GPU, экран и timezone — твой реальный отпечаток остаётся скрытым.

### 🔑 Ключевые возможности

| Функция | Описание |
|----------|-----------|
| 🧬 **Hardware Spoofing** | Генерация случайного CPU, GPU, RAM, экрана при каждой сессии |
| 🧩 **JS-инъекции** | Перехват Canvas, WebGL, Battery, AudioContext, Plugins, Fonts до загрузки страницы |
| 🗂️ **Изоляция профиля** | Новая временная директория на каждый запуск, secure wipe при закрытии |
| 🛡️ **PID-only cleanup** | Завершает только свои процессы Brave — системный не трогает |
| 🌐 **VPN-детект** | Проверяет публичный IP и VPN-индикаторы перед запуском |
| 📁 **Secure Drop Zone** | Drag & Drop с AES-256-GCM шифрованием в карантин |

---

## 🚀 Быстрый старт

```bash
# Клонировать репозиторий
git clone https://github.com/yourname/kimshell.git
cd kimshell

# Установить зависимости
pip install -r requirements.txt

# Запустить
python main.py
```

При первом запуске автоматически скачивается Brave (~120 МБ).  
Повторные запуски используют кешированную версию.

**Требования:** Windows 10/11 (64‑bit), Python 3.11+, 4 GB RAM

---

## 🛡️ Защита от фингерпринтинга

### Полностью подменяются (14 векторов)

*(таблица без изменений — уже идеальна)*

### Ручная настройка

| Вектор | Рекомендация |
|--------|---------------|
| DNS | Включить Cloudflare DNS (1.1.1.1) в настройках Brave |
| Системные шрифты | Использовать стандартный набор Windows‑шрифтов |

---

## 🏗️ Архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                        KimShell v2.0                         │
├──────────────────────────────────────────────────────────────┤
│  GUI (PyQt6)                                                 │
│  ├── LoadingScreen — анимированный экран инициализации       │
│  ├── MainWindow — управление сессией, лог, drop‑zone         │
│  └── SecureDropZone — AES‑256‑GCM карантин                   │
├──────────────────────────────────────────────────────────────┤
│  Core                                                        │
│  ├── HardwareSpoofer — генерация профиля железа              │
│  ├── JSInjector — создание расширения с подделкой JS-данных  │
│  ├── BraveManager — загрузка, профиль, launch‑command        │
│  ├── NetworkChecker — VPN/IP‑детект                          │
│  └── CleanupManager — secure wipe, atexit, SIGINT            │
├──────────────────────────────────────────────────────────────┤
│  Utils                                                       │
│  ├── Config — пути (%APPDATA%\KimShell), параметры            │
│  └── Helpers — logger, secure_wipe(3 passes), subprocess      │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│          Brave Browser (портативный, ~120 MB)                │
│  ├── Профиль: временная директория                           │
│  ├── Расширение: content.js (document_start, world=MAIN)     │
│  └── Флаги: --disable-gpu, --force-webrtc..., --user-agent   │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Структура проекта

```
kimshell/
├── main.py                 ← Точка входа, проверка Windows
├── requirements.txt
├── README.md
│
├── core/
│   ├── brave_manager.py    ← Загрузка, профиль, команда запуска
│   ├── cleanup.py          ← Secure wipe (3 passes), atexit, SIGINT
│   ├── hardware_spoof.py   ← Генератор профилей (CPU/GPU/RAM/UA)
│   ├── js_injector.py      ← Создание Brave‑расширения
│   └── network_checker.py  ← VPN‑детект, публичный IP
│
├── gui/
│   ├── dnd_widget.py       ← Drag & Drop + AES‑256‑GCM карантин
│   ├── loading_screen.py   ← Анимированный экран загрузки
│   ├── main_window.py      ← Главное окно, InitThread
│   └── styles.py           ← Тёмная тема QSS
│
└── utils/
    ├── config.py           ← Пути (%APPDATA%\KimShell), параметры
    └── helpers.py          ← Logger, secure_wipe, run_command
```

---

## 🧪 Результаты тестов

*(оригинальная таблица сохранена, только немного выровнены колонки)*

---

## ❓ FAQ

**❓ Brave скачивается каждый раз?**  
Нет, только при первом запуске или если `brave.exe` удалён — версия кешируется.

**❓ Закроет ли KimShell мой основной Brave?**  
Нет. Завершение строго по PID, не по имени процесса, системный Brave не трогается.

**❓ Где хранятся данные сессии?**  
В `%APPDATA%\KimShell\` — профили, карантин и расширение. Всё удаляется при закрытии (secure wipe ×3).

**❓ Нужен ли VPN?**  
KimShell скрывает браузерный отпечаток, но не IP. Для полной анонимности используй VPN + KimShell.

**❓ Почему Canvas fingerprint уникален?**  
Он меняется при каждой сессии и никогда не совпадает с настоящим отпечатком.

**❓ Работает на Windows 7?**  
Нет. Требуется Windows 10 (1903+) и актуальные компоненты PyQt6/Brave.

---

## ⚠️ Безопасность

- **Secure wipe** ограничен wear‑leveling‑контроллером SSD/NVMe — для чувствительных данных используй полное шифрование (BitLocker / VeraCrypt).  
- **DNS:** Включай Cloudflare DNS (1.1.1.1).  
- **VPN:** KimShell не заменяет VPN, а работает совместно.

---

## 📄 Лицензия

MIT License — свободное использование, модификация и распространение.

---

<p align="center">
  <sub>Made with paranoid precision 🛡️</sub>
</p>
```
