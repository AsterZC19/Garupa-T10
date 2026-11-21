import threading
import time


class TTLCache:
    def __init__(self, ttl_seconds, maxsize=None):
        self.ttl_seconds = ttl_seconds
        self.maxsize = maxsize
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if time.time() - item['time'] >= self.ttl_seconds:
                self._data.pop(key, None)
                return None
            return item['value']

    def set(self, key, value):
        now = time.time()
        with self._lock:
            if self.maxsize is not None and key not in self._data and len(self._data) >= self.maxsize:
                expired_keys = [
                    k for k, v in self._data.items()
                    if now - v['time'] >= self.ttl_seconds
                ]
                for k in expired_keys:
                    self._data.pop(k, None)
                while len(self._data) >= self.maxsize and self._data:
                    oldest_key = min(self._data, key=lambda k: self._data[k]['time'])
                    self._data.pop(oldest_key, None)
            self._data[key] = {'time': now, 'value': value}
            return value

    def clear(self):
        with self._lock:
            self._data.clear()
