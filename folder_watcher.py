from __future__ import annotations
import os
import time
import signal  # Module for handling system signals
from typing import Optional, Set, Iterable
import multiprocessing
import queue as _queue_exc  # for handling queue.Full if needed
from config import config_


"""
Function `<run_watcher>` is designed to run in a separate process
(for example, via multiprocessing.Process). It receives a constant path and
a queue object (multiprocessing.Queue) once during process initialization.

When immediate child folders appear/are deleted in the specified directory,
a dictionary is placed in the queue:
 - {"event": "new", "folder_name": "<folder_name>"}
 - {"event": "del", "folder_name": "<folder_name>"}

Reaction is based on simple polling (we check the directory at regular intervals).
"""


# Base directory that we monitor for new folders
# Get storage path from configuration module
STORAGE_PATH = config_.STORAGE_DIR
# Global flag for termination signal
_terminate_requested = False


def _handle_terminate(signum, frame) -> None:  # pragma: no cover - simple signal wrapper
    # Access global termination flag
    global _terminate_requested
    # Set termination flag to True
    _terminate_requested = True


def _list_child_folders(path: str, include_hidden: bool) -> Set[str]:
    # Create empty set for folder names
    names: Set[str] = set()
    try:
        # Open directory for scanning
        with os.scandir(path) as it:
            # Iterate through all directory entries
            for entry in it:
                try:
                    # Check if entry is a directory (not following symlinks)
                    if not entry.is_dir(follow_symlinks=False):
                        # Skip if not a directory
                        continue
                except OSError:
                    # Entry might disappear during check
                    # Skip this entry
                    continue
                # Get entry name
                name = entry.name
                # Check if hidden file (starts with '.') and include_hidden is False
                if not include_hidden and name.startswith("."):
                    # Skip hidden files
                    continue
                # Add name to set
                names.add(name)
    except (PermissionError, FileNotFoundError):
        # If no access or directory deleted - return empty set
        return set()
    # Return set of folder names
    return names


def _safe_put(out_queue, payload: dict) -> None:
    """
    Put item in queue without blocking the calling process forever and without crashing on errors.
    If queue is full or closed, the event is skipped.
    """
    try:
        # Try non-blocking put. multiprocessing.Queue.put(block=False) works.
        out_queue.put(payload, block=False)
    except TypeError:
        # Some queues (or old implementations) might not support block kwarg.
        try:
            # Try regular blocking put
            out_queue.put(payload)
        except Exception:
            # Ignore any exception
            pass
    except (BrokenPipeError, EOFError, _queue_exc.Full, OSError):
        # Queue closed, receiver process finished, or queue full
        # Ignore and continue
        pass
    except Exception:
        # Any other error - ignore to not interrupt watcher
        pass


def run_watcher(
    out_queue,
    poll_interval: float = 1.0,
    include_hidden: bool = False,
    stop_event: Optional[multiprocessing.synchronize.Event] = None,
) -> None:
    """
    Start blocking watcher in current process.

    Parameters:
      path: path to directory (string). Should exist and be a directory.
      out_queue: queue object (usually multiprocessing.Queue) where event
                 dictionaries will be placed.
      poll_interval: polling interval in seconds (float, >= 0.1 recommended).
      include_hidden: if False, ignore names starting with '.'.
      stop_event: (optional) multiprocessing.Event - if provided, will be checked
                  for is_set() for proper stop from another process.

    Behavior:
      - Function blocks current process and runs until:
          * stop_event is set (if provided), or
          * SIGTERM/SIGINT signal is sent to process, or
          * process is forcibly terminated.
      - At start, previous folder set is set to current directory state,
        so no initial events are generated for already existing folders.
    """
    # Access global termination flag
    global _terminate_requested

    # Check if storage path exists
    if not os.path.exists(STORAGE_PATH):
        # Raise error if path not found
        raise FileNotFoundError(f"Path not found: {STORAGE_PATH}")

    # Set signal handlers for clean termination on SIGTERM/SIGINT.
    # This is safe: we override signal only in watcher process.
    # Set handler for SIGTERM signal
    signal.signal(signal.SIGTERM, _handle_terminate)
    try:
        # Try to set handler for SIGINT signal
        signal.signal(signal.SIGINT, _handle_terminate)
    except Exception:
        # On some platforms (Windows) there might be SIGINT handling restrictions
        # Continue without SIGINT handler
        pass

    # Initial state: existing folders are not considered "new".
    # Get current list of child folders
    previous: Set[str] = _list_child_folders(STORAGE_PATH, include_hidden)

    # Small lower bound for poll_interval for proper reaction and CPU saving.
    # Check if poll_interval is negative
    if poll_interval < 0:
        # Set to zero if negative
        poll_interval = 0.0

    # Main polling loop
    while True:
        # Check external stop event (multiprocessing.Event supports is_set()).
        # Check if stop_event is provided
        if stop_event is not None:
            try:
                # Check if event is set
                if stop_event.is_set():
                    # Break loop if event is set
                    break
            except Exception:
                # If event is wrong type or invalid - ignore
                pass

        # Check termination flag from signal
        # Check if termination requested
        if _terminate_requested:
            # Break loop if termination requested
            break

        # Get current list of folders
        current = _list_child_folders(STORAGE_PATH, include_hidden)
        # Find newly added folders (in current but not in previous)
        added = current - previous
        # Find removed folders (in previous but not in current)
        removed = previous - current

        # Generate events (sort for deterministic order)
        # Process added folders
        for name in sorted(added):
            # Create payload dictionary
            payload = {"event": "new", "folder_name": name}
            # Put payload in queue
            _safe_put(out_queue, payload)

        # Process removed folders
        for name in sorted(removed):
            # Create payload dictionary
            payload = {"event": "del", "folder_name": name}
            # Put payload in queue
            _safe_put(out_queue, payload)

        # Update previous state to current
        previous = current

        # Waiting: if stop_event provided, can wait via its wait() (faster response).
        # Check if stop_event exists and has wait method
        if stop_event is not None and hasattr(stop_event, "wait"):
            try:
                # wait returns True if event is set - then break loop
                # Wait with timeout
                signaled = stop_event.wait(timeout=poll_interval)
                # Check if event was signaled
                if signaled:
                    # Break loop if signaled
                    break
            except Exception:
                # If wait not available or caused error - fallback to time.sleep
                # Sleep for poll interval
                time.sleep(poll_interval)
        else:
            # Sleep in short intervals to react to signals faster
            # Track time slept
            slept = 0.0
            # Calculate sleep step
            step = min(0.1, poll_interval) if poll_interval > 0 else 0.1
            # Sleep in small steps
            while slept < poll_interval and not _terminate_requested:
                # Sleep for step duration
                time.sleep(step)
                # Add step to total slept time
                slept += step
                # Additional stop_event check in case it was set externally without wait()
                # Check if stop_event exists
                if stop_event is not None:
                    try:
                        # Check if event is set
                        if stop_event.is_set():
                            # Set termination flag
                            _terminate_requested = True
                            # Break inner loop
                            break
                    except Exception:
                        # Ignore any exception
                        pass

    # Before exit, we could try to put final events, but usually not needed.
    # Return from function
    return