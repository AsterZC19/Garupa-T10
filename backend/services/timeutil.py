# backend/services/timeutil.py
"""全项目统一的时间基准。

所有「当前时刻的 unix 毫秒」都应从这里取 now_ms()，不要再各写各的
`datetime.utcnow().timestamp()*1000`（在非 UTC 系统会偏差数小时）、
`datetime.now().timestamp()*1000` 或 `time.time()*1000`。
"""
import time

HOUR_MS = 3600000
DAY_MS = 86400000


def now_ms():
    """当前时刻的 unix 毫秒（UTC，真实时刻）。"""
    return int(time.time() * 1000)
