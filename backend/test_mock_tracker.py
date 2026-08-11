"""模拟 GarupaSpeedTracker 后端：返回符合参考 API 结构的月榜数据，用于本地验证管道。"""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_TS = int(time.time() * 1000)
DAY = 86400000

# 两个玩家，两天历史，每分钟一条
UIDS = [11111111, 22222222, 33333333, 44444444, 55555555,
        66666666, 77777777, 88888888, 99999999, 100000000]
NAMES = ['PlayerA', 'PlayerB', 'PlayerC', 'PlayerD', 'PlayerE',
         'PlayerF', 'PlayerG', 'PlayerH', 'PlayerI', 'PlayerJ']

PERIOD = {
    '22': {
        'monthlyRankingName': ['2026年7月度 月間ランキング', None, None, None, None],
        'assetBundleName': 'monthly_ranking_202607',
        'bgmFileName': 'bgm_monthly_202607',
        'startAt': [BASE_TS - 31 * DAY, None, None, None, None],
        'endAt': [BASE_TS - DAY, None, None, None, None],
    },
    '23': {
        'monthlyRankingName': ['2026年8月度 月間ランキング', None, None, None, None],
        'assetBundleName': 'monthly_ranking_202608',
        'bgmFileName': 'bgm_monthly_202608',
        'startAt': [BASE_TS, None, None, None, None],
        'endAt': [BASE_TS + 30 * DAY, None, None, None, None],
    },
}


def build_points(monthly_id, n=60):
    """生成 n 条逐点快照（每小时一条，覆盖 2.5 天）。"""
    period = PERIOD[str(monthly_id)]
    start = int(period['startAt'][0])
    points = []
    for i in range(n):
        ts = start + i * 3600000
        for j, uid in enumerate(UIDS):
            base = (j + 1) * 100000
            growth = i * (j + 1) * 500
            points.append({'time': ts, 'uid': uid, 'value': base + growth})
    return points


def build_users():
    users = []
    for j, uid in enumerate(UIDS):
        users.append({
            'uid': uid,
            'name': NAMES[j],
            'introduction': f'player {NAMES[j]} intro',
            'rank': j + 1,
            'sid': 1,
            'strained': 0,
            'degrees': [],
        })
    return users


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        body = None
        if path.endswith('/monthlyRanking/info.json'):
            body = PERIOD
        elif path.endswith('/monthlyRanking/top.json') or path.endswith('/monthlyRanking/top'):
            monthly_id = int((params.get('monthlyId') or ['23'])[0])
            body = {'points': build_points(monthly_id), 'users': build_users()}
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(body).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    print('mock tracker on 5519')
    HTTPServer(('127.0.0.1', 55199), Handler).serve_forever()
