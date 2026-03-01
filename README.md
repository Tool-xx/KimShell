```markdown
# KimShell v2.0

```
██╗  ██╗██╗███╗   ███╗███████╗██╗  ██╗███████╗██╗     ██╗     
██║ ██╔╝██║████╗ ████║██╔════╝██║  ██║██╔════╝██║     ██║     
█████╔╝ ██║██╔████╔██║███████╗███████║█████╗  ██║     ██║     
██╔═██╗ ██║██║╚██╔╝██║╚════██║██╔══██║██╔══╝  ██║     ██║     
██║  ██╗██║██║ ╚═╝ ██║███████║██║  ██║███████╗███████╗███████╗
╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
```

**Secure Browser Environment** — изолированный браузер Brave с полным спуфингом аппаратного отпечатка и защитой от фингерпринтинга.

![Python](https://img.shields.io/badge/Python-3.11%2B-00ff88?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-00d4ff?style=flat-square&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-ff3366?style=flat-square)

[📖 Documentation](https://yourname.github.io/kimshell) · [🚀 Releases](https://github.com/yourname/kimshell/releases) · [🐛 Issues](https://github.com/yourname/kimshell/issues)

---

## 🎯 Что делает

KimShell создаёт временный изолированный профиль Brave Browser с поддельными характеристиками компьютера. Сайты видят несуществующий CPU, GPU, экран и timezone — твой реальный отпечаток остаётся скрытым.

**Ключевые возможности:**

| Функция | Описание |
|---------|----------|
| 🧬 **Hardware Spoofing** | Случайный CPU (AMD/Intel), GPU (NVIDIA/AMD), RAM, экран каждую сессию |
| 🧩 **JS-инъекции** | Перехват Canvas, WebGL, Battery, AudioContext, Plugins, Fonts до загрузки страницы |
| 🗂️ **Изоляция профиля** | Новая временная директория на каждый запуск, secure wipe при закрытии |
| 🛡️ **PID-only cleanup** | Завершение только своих процессов Brave, системный браузер не трогается |
| 🌐 **VPN-детект** | Проверка публичного IP и VPN-индикаторов перед запуском |
| 📁 **Secure Drop Zone** | Drag & Drop с AES-256-GCM шифрованием в карантин |

---

## 🚀 Быстрый старт

```bash
# Клонировать
git clone https://github.com/yourname/kimshell.git
cd kimshell

# Установить зависимости
pip install -r requirements.txt

# Запустить
python main.py
```

При первом запуске автоматически скачается Brave (~120 МБ). В последующие — используется кешированная версия.

**Требования:** Windows 10/11 (64-bit), Python 3.11+, 4GB RAM

---

## 🛡️ Защита от фингерпринтинга

### Полностью подменяется (14 векторов):

| Вектор | Метод | Статус |
|--------|-------|--------|
| Canvas 2D | `getImageData` noise ±1 | ✅ SPOOFED |
| WebGL Vendor | `getParameter(UNMASKED_VENDOR)` | ✅ SPOOFED |
| CPU Cores | `navigator.hardwareConcurrency` | ✅ SPOOFED |
| Device Memory | `navigator.deviceMemory` | ✅ SPOOFED |
| Timezone | `Date.getTimezoneOffset()` + `Intl` | ✅ SPOOFED |
| Battery API | `navigator.getBattery()` | ✅ SPOOFED |
| Media Devices | `enumerateDevices()` | ✅ SPOOFED |
| Plugins | `navigator.plugins` (PDF list) | ✅ SPOOFED |
| AudioContext | `getFloatFrequencyData` noise | ✅ SPOOFED |
| Font Metrics | `getComputedStyle` jitter | ✅ SPOOFED |
| Sensors | `permissions.query()` → denied | ✅ BLOCKED |
| WebRTC | `--force-webrtc-ip-handling-policy` | ✅ BLOCKED |
| Screen | JS + `--window-size` | ✅ SPOOFED |
| User-Agent | JS + `--user-agent` | ✅ SPOOFED |

### Требует ручной настройки:

| Вектор | Рекомендация |
|--------|--------------|
| DNS | Включить Cloudflare DNS (1.1.1.1) в настройках Brave |
| Системные шрифты | Использовать стандартный набор Windows-шрифтов |

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    KimShell v2.0                            │
├─────────────────────────────────────────────────────────────┤
│  GUI (PyQt6)                                                │
│  ├── LoadingScreen — анимированный экран инициализации      │
│  ├── MainWindow — управление сессией, лог, дроп-зона        │
│  └── SecureDropZone — AES-256-GCM карантин                  │
├─────────────────────────────────────────────────────────────┤
│  Core                                                        │
│  ├── HardwareSpoofer — генерация профиля железа             │
│  ├── JSInjector — создание расширения с реальными значениями│
│  ├── BraveManager — загрузка, профиль, launch command        │
│  ├── NetworkChecker — VPN/IP детект                         │
│  └── CleanupManager — secure wipe, atexit, SIGINT           │
├─────────────────────────────────────────────────────────────┤
│  Utils                                                       │
│  ├── Config — пути (%APPDATA%\KimShell), параметры            │
│  └── Helpers — logger, secure_wipe(3 passes), subprocess      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Brave Browser (портативный, ~120MB)                        │
│  ├── Профиль: временная директория                          │
│  ├── Расширение: content.js (document_start, world=MAIN)    │
│  └── Флаги: --disable-gpu, --force-webrtc..., --user-agent  │
└─────────────────────────────────────────────────────────────┘
```

**Поток данных:**
1. `HardwareSpoofer.generate_profile(seed)` → случайный профиль
2. `to_brave_flags()` → CLI-аргументы для Brave
3. `JSInjector.create_extension(profile)` → content.js с подстановкой значений
4. `BraveManager.create_profile()` → Preferences (window size, shields, clear-on-exit)
5. `Popen(cmd, env=env)` → запуск с `CREATE_NEW_PROCESS_GROUP`
6. PID записывается → `taskkill /T /PID <pid>` при cleanup (не `/IM brave.exe`)

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
│   ├── js_injector.py      ← Создание Brave-расширения
│   └── network_checker.py  ← VPN-детект, публичный IP
│
├── gui/
│   ├── dnd_widget.py       ← Drag & Drop + AES-256-GCM карантин
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

Проверено на [coveryourtracks.eff.org](https://coveryourtracks.eff.org) и [browserleaks.com](https://browserleaks.com):

| Тест | Результат |
|------|-----------|
| Tracking ads | ❌ BLOCKED |
| Invisible trackers | ❌ BLOCKED |
| WebRTC IP leak | ❌ NO LEAK |
| Timezone | 🎭 SPOOFED |
| Battery API | 🎭 SPOOFED |
| WebGL Vendor | 🎭 SPOOFED |
| Canvas fingerprint | 🎭 NOISED (unique per session) |
| Media devices | 🎭 SPOOFED (2 generic devices) |
| Plugins | 🎭 SPOOFED (PDF viewers only) |
| User-Agent | 🎭 SPOOFED |

---

## ❓ FAQ

**Q: Brave скачивается каждый раз?**  
A: Нет. Только при первом запуске или если `brave.exe` удалён. Версия кешируется в `.version`.

**Q: Закроет ли KimShell мой основной Brave?**  
A: Нет. Завершение строго по PID, не по имени процесса. Твои закладки и сессии в системном Brave сохраняются.

**Q: Где хранятся данные сессии?**  
A: `%APPDATA%\KimShell\` — профили, карантин, расширение. Удаляется при закрытии с secure wipe (3 прохода: 0x00 → 0xFF → random).

**Q: Нужен ли VPN?**  
A: KimShell скрывает браузерный отпечаток, но не IP-адрес. Для полной анонимности используй VPN + KimShell.

**Q: Почему Canvas fingerprint уникален?**  
A: Это цель — он меняется каждую сессию и не совпадает с твоим реальным браузером.

**Q: Работает на Windows 7?**  
A: Нет. Требуется Windows 10 1903+ для PyQt6 и актуальных версий Brave.

---

## ⚠️ Безопасность

- **Secure wipe** на SSD/NVMe ограничен wear leveling контроллером — для критичных данных используй шифрование диска (BitLocker/VeraCrypt)
- **DNS**: Включи Cloudflare DNS (1.1.1.1) в настройках Brave для защиты от DNS-утечек
- **VPN**: KimShell не заменяет VPN — используй вместе

---

## 📄 Лицензия

MIT License — свободное использование, модификация и распространение.

---

<p align="center">
  <sub>Made with paranoid precision 🛡️</sub>
</p>
```