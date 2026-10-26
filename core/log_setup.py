"""Log files for the backend (backend/logs/, or LOG_DIR). One file per day, named by date (scheduler-2026-10-26.log), old ones removed after
`keep_days`. Written in append mode and never renamed, so the web server and the Windows scheduler service can both write to the same
folder (Python's own rotating handler renames the file at midnight, which fails on Windows while another process has it open)."""

import datetime
import logging
import os


class DailyFileHandler(logging.Handler):
    def __init__(self, folder, prefix, keep_days=60, level=logging.NOTSET):
        super().__init__(level)
        self.folder, self.prefix, self.keep_days = str(folder), prefix, int(keep_days)
        self._day = None
        self._stream = None

    def _open(self, day):
        os.makedirs(self.folder, exist_ok=True)
        if self._stream:
            try:
                self._stream.close()
            except OSError:
                pass
        self._stream = open(os.path.join(self.folder, f"{self.prefix}-{day.isoformat()}.log"), "a", encoding="utf-8")
        self._day = day
        self._prune(day)

    def _prune(self, today):
        cutoff = today - datetime.timedelta(days=self.keep_days)
        try:
            for name in os.listdir(self.folder):
                if name.startswith(self.prefix + "-") and name.endswith(".log"):
                    try:
                        d = datetime.date.fromisoformat(name[len(self.prefix) + 1 : -4])
                    except ValueError:
                        continue
                    if d < cutoff:
                        os.remove(os.path.join(self.folder, name))
        except OSError:
            pass

    def emit(self, record):
        try:
            day = datetime.date.today()
            if self._stream is None or day != self._day:
                self._open(day)
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        try:
            if self._stream:
                self._stream.close()
        finally:
            super().close()
