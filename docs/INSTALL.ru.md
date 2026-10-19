# Установка Emberbox Audio

[English](INSTALL.md) · **Русский**

## Что нужно

- Linux с X11 либо Wayland с включённым XWayland.
- Python 3.10+, GTK 3 и PyGObject.
- PipeWire и утилиты `pw-record`, `pw-link`, `pw-dump`.
- Клиент Spotify, MPRIS и pactl для громкости приложения; numpy, Pillow и websocket-client.

Проверенная система: **LunaOS (на базе Arch), GNOME 50, Wayland + XWayland**. Размещение настольного окна зависит от композитора. Команды для других дистрибутивов устанавливают зависимости; полная работа во всех окружениях пока не проверена.

### Arch и производные

```sh
sudo pacman -S --needed python python-gobject gtk3 python-numpy python-pillow pipewire-audio libpulse python-websocket-client
```

### Ubuntu / семейство Debian

Названия пакетов соответствуют Ubuntu 24.04; рекомендуется свежий дистрибутив.

```sh
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 python3-numpy python3-pil pipewire-bin pulseaudio-utils python3-websocket

```

Spotify устанавливается отдельно: обычный исполняемый файл `spotify` либо Flatpak `com.spotify.Client`. Emberbox сам не устанавливает и не изменяет Spotify.

Проверка без изменения системы:

```sh
python3 tools/check_dependencies.py
```

Нужен Python, которому доступен модуль `gi`. Для виртуального окружения используй `--system-site-packages`. Нативные GTK- и аудиозависимости не устанавливаются через `requirements.txt`.

Для необязательных видеообложек Apple Music нужен `ffmpeg`: `sudo pacman -S ffmpeg` или `sudo apt install ffmpeg`. Крупные статичные обложки работают без него. [Подробнее](FULLSCREEN.ru.md).

## Установка для текущего пользователя

```sh
./install.sh                 # пункт меню, запуск по желанию
./install.sh --autostart     # дополнительно включить запуск при входе
```

Сам установщик не использует `sudo` и ничего не скачивает. Он создаёт пользовательскую службу systemd, пункт меню и небольшую команду запуска. Открой **Emberbox Audio** в меню либо выполни `~/.local/bin/emberbox-audio`. Медиа автоматически не включается.

Файлы приложения находятся в `$XDG_DATA_HOME/emberbox-audio` (по умолчанию `~/.local/share/emberbox-audio`). Настройки и кеш — в `$XDG_CONFIG_HOME/emberbox-audio` и `$XDG_CACHE_HOME/emberbox-audio`. Чужой каталог установщик перезаписывать отказывается.

Без пользовательского systemd:

```sh
./install.sh --no-systemd
# --no-systemd --autostart создаст запись автозапуска XDG
```

Запуск из исходников:

```sh
./run.sh
```

`GDK_BACKEND=x11` выбран намеренно: настольные подсказки оконному менеджеру и встроенное видео используют X11. Сам сеанс Wayland остаётся включённым.

## Остановка, обновление, удаление

```sh
systemctl --user stop emberbox-audio.service
# после обновления исходников:
./install.sh
# удаление:
./uninstall.sh
```

Удаляются файлы приложения и его запускатели. Личные настройки и кеш сохраняются. Для полного сброса соответствующие каталоги XDG можно удалить вручную. Тема рабочего стола, Spotify и профиль браузера не меняются.

## Если что-то не работает

- Нет окна: запусти `./run.sh` из терминала и проверь зависимости и XWayland.
- Окно под приложениями: это нормальное поведение настольного виджета; вернись на рабочий стол.
- Лампы неподвижны: проверь `pw-link -l` и наличие звука у нужного приложения. Аудиопорты Spotify должны быть видны в PipeWire хоста.
- Нет звука: проверь тумблер, крутилку и системный микшер приложений.
- Журнал службы: `journalctl --user -u emberbox-audio.service -n 40`.

## Apple Music

Вместо клиента Spotify можно выбрать браузер Linux с MPRIS. См. [подключение и ограничения](APPLE_MUSIC.ru.md).
