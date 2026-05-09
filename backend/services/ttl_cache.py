import time


class TTLCache:
    def __init__(self, ttl_seconds):
        self.ttl_seconds = ttl_seconds
        self._data = {}

    def get(self, key):
        item = self._data.get(key)
        if not item:
            return None
        if time.time() - item['time'] >= self.ttl_seconds:
            self._data.pop(key, None)
            return None
        return item['value']

    def set(self, key, value):
        self._data[key] = {'time': time.time(), 'value': value}
        return value

    def clear(self):
        self._data.clear()
