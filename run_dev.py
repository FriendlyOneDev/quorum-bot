#!/usr/bin/env python3
"""Dev runner that auto-reloads the bot when .py files change."""

import subprocess
import sys
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ReloadHandler(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.start_bot()

    def start_bot(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            print("\n--- Restarting bot ---\n")
        self.process = subprocess.Popen([sys.executable, "-m", "bot.main"])

    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            self.start_bot()

    def on_created(self, event):
        if event.src_path.endswith(".py"):
            self.start_bot()


if __name__ == "__main__":
    handler = ReloadHandler()
    observer = Observer()
    observer.schedule(handler, ".", recursive=True)
    observer.start()

    print("Watching for .py changes... (Ctrl+C to stop)\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if handler.process:
            handler.process.terminate()
    observer.join()
