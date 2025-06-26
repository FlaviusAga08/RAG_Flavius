from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Thread
import time

class DirectoryChangeHandler(FileSystemEventHandler):
    def __init__(self, indexer):
        self.indexer = indexer

    def on_created(self, event):
        if not event.is_directory:
            print(f"[Watcher] New file: {event.src_path}")
            self.indexer._index_all_documents_sync()

    def on_modified(self, event):
        if not event.is_directory:
            print(f"[Watcher] Modified file: {event.src_path}")
            self.indexer._index_all_documents_sync()

def start_directory_watcher(path: str, indexer):
    def run():
        observer = Observer()
        handler = DirectoryChangeHandler(indexer)
        observer.schedule(handler, path=path, recursive=True)
        observer.start()
        print(f"[Watcher] Watching {path}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    thread = Thread(target=run, daemon=True)
    thread.start()
