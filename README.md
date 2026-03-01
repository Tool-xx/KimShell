# KimShell

```
██╗  ██╗██╗███╗   ███╗███████╗██╗  ██╗███████╗██╗     ██╗
██║ ██╔╝██║████╗ ████║██╔════╝██║  ██║██╔════╝██║     ██║
█████╔╝ ██║██╔████╔██║███████╗███████║█████╗  ██║     ██║
██╔═██╗ ██║██║╚██╔╝██║╚════██║██╔══██║██╔══╝  ██║     ██║
██║  ██╗██║██║ ╚═╝ ██║███████║██║  ██║███████╗███████╗███████╗
╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
```

<p align="center">
<b>Secure Browser Environment</b><br>
Изолированная среда Brave с аппаратным spoofing и анти-фингерпринтингом
</p>

<p align="center">
<img src="https://img.shields.io/badge/Python-3.11%2B-00ff88?style=flat-square&logo=python&logoColor=white">
<img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-00d4ff?style=flat-square&logo=windows&logoColor=white">
</p>

<p align="center">
<a href="https://github.com/Tool-xx/KimShell">Repository</a> ·
<a href="https://github.com/Tool-xx/KimShell/releases">Releases</a> ·
<a href="https://github.com/Tool-xx/KimShell/issues">Issues</a>
</p>

---

## О проекте

**KimShell** создаёт полностью изолированную временную среду Brave Browser с подменой аппаратного отпечатка.

Сайты видят:

- Несуществующий CPU  
- Случайный GPU  
- Изменённый экран  
- Подменённый timezone  

Реальный fingerprint системы не используется.

---

## Ключевые возможности

### Hardware Spoofing

- Случайный CPU (AMD / Intel)
- GPU (NVIDIA / AMD)
- RAM
- Screen resolution
- Новый профиль каждую сессию

### JS-инъекции (document_start)

Перехват до загрузки страницы:

- Canvas
- WebGL
- AudioContext
- Battery API
- Plugins
- Media Devices
- Fonts
- Sensors
- Timezone

### Полная изоляция

- Временный профиль
- Отдельная директория
- Secure wipe при завершении
- PID-based cleanup (без `taskkill /IM`)

### Network-контроль

- Проверка публичного IP
- Детект VPN
- WebRTC блокировка

### Secure Drop Zone

- Drag & Drop
- AES-256-GCM шифрование
- Карантинная директория

---

## Быстрый старт (запускать через консоль которая запущенна от имени администратора!)

```bash
git clone https://github.com/Tool-xx/KimShell.git
cd KimShell
pip install -r requirements.txt
python main.py
```

При первом запуске автоматически загружается Brave (~120MB).  
Далее используется кешированная версия.

### Требования

- Windows 10 / 11 (64-bit)
- Python 3.11+
- 4 GB RAM

---

## Защита от фингерпринтинга

### Подменяется автоматически

| Вектор        | Статус     |
|---------------|------------|
| Canvas        | ✅ |
| WebGL Vendor  | ✅ |
| CPU Cores     | ✅ |
| Device Memory | ✅ |
| Timezone      | ✅ |
| Battery API   | ✅ |
| Media Devices | ✅ |
| Plugins       | ✅ |
| AudioContext  | ✅ |
| Fonts         | ✅ |
| Screen        | ✅ |
| User-Agent    | ✅ |
| WebRTC        | 🚫 Blocked |
| Sensors       | 🚫 Blocked |

### Требует ручной настройки

| Вектор | Рекомендация |
|--------|--------------|
| DNS    | Включить 1.1.1.1 |
| VPN    | Использовать отдельно |

---

## Архитектура

```
GUI (PyQt6)
 ├── LoadingScreen
 ├── MainWindow
 └── SecureDropZone

Core
 ├── HardwareSpoofer
 ├── JSInjector
 ├── BraveManager
 ├── NetworkChecker
 └── CleanupManager

Utils
 ├── Config
 └── Helpers
```

Brave запускается:

- С временным профилем  
- Через CLI-флаги  
- С расширением `content.js` (document_start)  
- В отдельной process group  

---

## Структура проекта

```
KimShell/
├── main.py
├── core/
├── gui/
├── utils/
└── requirements.txt
```

---

## Тестирование

Проверено на:

- coveryourtracks.eff.org  
- browserleaks.com  

Результаты:

- WebRTC leak — отсутствует  
- Canvas — уникален для каждой сессии  
- WebGL — spoofed  
- Tracking — blocked  

---

## FAQ

**Brave скачивается каждый раз?**  
Нет. Только при первом запуске.

**Закроется ли основной Brave?**  
Нет. Завершение строго по PID.

**Где хранятся данные?**  
`%APPDATA%\KimShell\`  
Удаляются при завершении (3-pass wipe).

**Заменяет ли VPN?**  
Нет. IP-адрес не скрывается.

**Почему Canvas уникальный?**  
Он меняется каждую сессию — это защита от трекинга.

---

<p align="center">
Built for controlled environments
</p>
