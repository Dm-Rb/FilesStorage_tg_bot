"""
Файл: folder_watcher.py

Блокирующая функция `run_watcher` предназначена для запуска в отдельном процессе
(например, через multiprocessing.Process). Ей передаётся константный путь и
объект очереди (multiprocessing.Queue) один раз при инициализации процесса.

При появлении/удалении непосредственных дочерних папок в указанном каталоге
в очередь помещается словарь:
 - {"event": "new", "folder_name": "<имя папки>"}
 - {"event": "del", "folder_name": "<имя папки>"}

Реакция основана на простом polling'е (опрашиваем каталог с заданным интервалом).
Этот модуль не создаёт глобальных процессов/потоков при импорте и безопасен для
использования с multiprocessing (spawn / fork).
"""

from __future__ import annotations
import os
import time
import signal
from typing import Optional, Set, Iterable

# Не импортируем тип Queue в аннотациях, чтобы не вызывать побочных эффектов.
# Обработка ошибок отправки в очередь выполнена мягко (игнорируются исключения).
import multiprocessing
import queue as _queue_exc  # для обработки queue.Full, если понадобится
from config import config_


# Base directory that we monitor for new folders
STORAGE_PATH = config_.STORAGE_DIR
_terminate_requested = False


def _handle_terminate(signum, frame) -> None:  # pragma: no cover - простая сигнальная обёртка
    global _terminate_requested
    _terminate_requested = True


def _list_child_folders(path: str, include_hidden: bool) -> Set[str]:
    names: Set[str] = set()
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    # Возможна ситуация, когда entry исчезает во время проверки
                    continue
                name = entry.name
                if not include_hidden and name.startswith("."):
                    continue
                names.add(name)
    except (PermissionError, FileNotFoundError):
        # Если нет доступа или каталог удалён — считаем, что список пуст.
        return set()
    return names


def _safe_put(out_queue, payload: dict) -> None:
    """
    Положить в очередь, не блокируя вызывающий процесс навсегда и не падая при ошибках.
    Если очередь заполнена или закрыта, событие пропускается.
    """
    try:
        # Попробуем не блокирующе. multiprocessing.Queue.put(block=False) работает.
        out_queue.put(payload, block=False)
    except TypeError:
        # Некоторые очереди (или старые реализаций) могут не поддерживать block kwarg.
        try:
            out_queue.put(payload)
        except Exception:
            pass
    except (BrokenPipeError, EOFError, _queue_exc.Full, OSError):
        # Очередь закрыта, процесс получателя завершён или очередь переполнена
        pass
    except Exception:
        # Любая другая ошибка — игнорируем, чтобы не прерывать watcher.
        pass


def run_watcher(
    out_queue,
    poll_interval: float = 1.0,
    include_hidden: bool = False,
    stop_event: Optional[multiprocessing.synchronize.Event] = None,
) -> None:
    """
    Запустить блокирующий watcher в текущем процессе.

    Параметры:
      path: путь к каталогу (строка). Должен существовать и быть каталогом.
      out_queue: объект очереди (обычно multiprocessing.Queue), в который будут
                 помещаться события-словарии.
      poll_interval: интервал опроса в секундах (float, >= 0.1 рекомендовано).
      include_hidden: если False, игнорируются имена, начинающиеся с '.'.
      stop_event: (опционально) multiprocessing.Event - если передан, будет проверяться
                  на is_set() для корректной остановки из другого процесса.

    Поведение:
      - Функция блокирует текущий процесс и работает до тех пор, пока:
          * не будет установлен stop_event (если он передан), либо
          * не будет отправлен SIGTERM/SIGINT процессу, либо
          * процесс не будет принудительно завершён.
      - При старте предыдущий набор папок устанавливается в текущее состояние каталога,
        поэтому начальных событий для уже существующих папок не генерируется.
    """
    global _terminate_requested

    if not os.path.exists(STORAGE_PATH):
        raise FileNotFoundError(f"Путь не найден: {STORAGE_PATH}")


    # Привязываем обработчики сигналов, чтобы корректно завершаться на SIGTERM/SIGINT.
    # Это безопасно: переопределим сигнал только в процессе watcher'а.
    signal.signal(signal.SIGTERM, _handle_terminate)
    try:
        signal.signal(signal.SIGINT, _handle_terminate)
    except Exception:
        # На некоторых платформах (Windows) может быть ограничение на обработку SIGINT
        pass

    # Начальное состояние: никакие существующие папки не считаются "новыми".
    previous: Set[str] = _list_child_folders(STORAGE_PATH, include_hidden)

    # Небольшая нижняя граница poll_interval для адекватной реакции и экономии CPU.
    if poll_interval < 0:
        poll_interval = 0.0

    # Цикл опроса
    while True:
        # Проверка внешнего события остановки (multiprocessing.Event поддерживает is_set()).
        if stop_event is not None:
            try:
                if stop_event.is_set():
                    break
            except Exception:
                # Если событие некорректного типа или невалидно — игнорируем.
                pass

        # Проверка флага завершения по сигналу
        if _terminate_requested:
            break

        current = _list_child_folders(STORAGE_PATH, include_hidden)
        added = current - previous
        removed = previous - current

        # Генерируем события (сортируем для детерминированного порядка)
        for name in sorted(added):
            payload = {"event": "new", "folder_name": name}
            _safe_put(out_queue, payload)

        for name in sorted(removed):
            payload = {"event": "del", "folder_name": name}
            _safe_put(out_queue, payload)

        previous = current

        # Ожидание: если передан stop_event, можно ждать через его wait() (быстрее реагирует).
        if stop_event is not None and hasattr(stop_event, "wait"):
            try:
                # wait вернёт True если событие установлено — тогда выйдем из цикла.
                signaled = stop_event.wait(timeout=poll_interval)
                if signaled:
                    break
            except Exception:
                # Если wait недоступен или вызвал ошибку — просто fallback на time.sleep
                time.sleep(poll_interval)
        else:
            # Спать короткими интервалами, чтобы реагировать на сигналы быстрее
            slept = 0.0
            step = min(0.1, poll_interval) if poll_interval > 0 else 0.1
            while slept < poll_interval and not _terminate_requested:
                time.sleep(step)
                slept += step
                # Дополнительная проверка stop_event в case оно было установлено извне без wait()
                if stop_event is not None:
                    try:
                        if stop_event.is_set():
                            _terminate_requested = True
                            break
                    except Exception:
                        pass

    # Перед выходом можно попытаться поставить финальные события, но обычно это не нужно.
    return