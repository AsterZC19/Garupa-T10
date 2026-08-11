# backend/services/garupa_protobuf.py
"""最小 protobuf wire 解码器（按参考项目 StarFreedomX/GarupaSpeedTracker 的
schema 定义驱动，无需 protoc 编译）。只实现月榜相关消息。

Schema 约定：{ 字段号: (字段名, 类型) }，类型为
  'int'/'long'/'bool'/'string'，或 ('msg', schema) 表示内嵌消息，
  或 ('msg_list', schema) 表示 repeated 内嵌消息。
"""


# ---------------------------------------------------------------------------
# Schema（移植自参考项目）
# ---------------------------------------------------------------------------

_MASTER_SCHEMA = {
    1: ('monthlyRankingId', 'int'),
    2: ('monthlyRankingName', 'string'),
    3: ('assetBundleName', 'string'),
    4: ('bgmAssetBundleName', 'string'),
    5: ('bgmFileName', 'string'),
    6: ('startAt', 'long'),
    7: ('endAt', 'long'),
    8: ('enableFlg', 'bool'),
    9: ('publicStartAt', 'long'),
    10: ('publicEndAt', 'long'),
    11: ('distributionStartAt', 'long'),
    12: ('distributionEndAt', 'long'),
    13: ('receptionEndAt', 'long'),
    14: ('aggregateEndAt', 'long'),
}

MASTER_LIST_SCHEMA = {
    1: ('entries', ('msg_list', _MASTER_SCHEMA)),
}

_RANKING_USER_SCHEMA = {
    1: ('name', 'string'),
    2: ('ownFlg', 'bool'),
    3: ('rankLevel', 'int'),
    4: ('introduction', 'string'),
    5: ('rank', 'int'),
    6: ('point', 'int'),
    7: ('userId', 'int'),
    8: ('degreeId', 'int'),
}

_RANKING_USER_LIST_SCHEMA = {
    1: ('entries', ('msg_list', _RANKING_USER_SCHEMA)),
}

# top/border 榜单响应：2=top、3=border（1=near，前端用不到）
RANKING_RESPONSE_SCHEMA = {
    1: ('monthlyRankingPointNearUsers', ('msg', _RANKING_USER_LIST_SCHEMA)),
    2: ('monthlyRankingPointTopUsers', ('msg', _RANKING_USER_LIST_SCHEMA)),
    3: ('monthlyRankingPointBorderUsers', ('msg', _RANKING_USER_LIST_SCHEMA)),
}


# ---------------------------------------------------------------------------
# Wire 解码
# ---------------------------------------------------------------------------

class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def eof(self):
        return self.pos >= len(self.data)

    def read_varint(self):
        shift = 0
        result = 0
        while True:
            b = self.data[self.pos]
            self.pos += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                return result
            shift += 7

    def read_bytes(self):
        length = self.read_varint()
        start = self.pos
        self.pos += length
        return self.data[start:start + length]


def _decode_message(data, schema):
    r = _Reader(data)
    out = {}
    while not r.eof():
        key = r.read_varint()
        field = key >> 3
        wire = key & 7
        spec = schema.get(field)
        if spec is None:
            # 跳过未知字段
            if wire == 0:
                r.read_varint()
            elif wire == 1:
                r.pos += 8
            elif wire == 2:
                r.read_bytes()
            elif wire == 5:
                r.pos += 4
            else:
                break
            continue

        name, type_ = spec

        if wire == 0:
            value = r.read_varint()
            if type_ == 'bool':
                value = bool(value)
        elif wire == 2:
            raw = r.read_bytes()
            if isinstance(type_, tuple):
                kind, sub = type_
                if kind == 'msg':
                    value = _decode_message(raw, sub)
                else:  # msg_list
                    value = _decode_message(raw, sub)
            elif type_ == 'string':
                value = raw.decode('utf-8', errors='replace')
            else:
                value = raw
        elif wire == 1:
            value = int.from_bytes(r.data[r.pos:r.pos + 8], 'little')
            r.pos += 8
        elif wire == 5:
            value = int.from_bytes(r.data[r.pos:r.pos + 4], 'little')
            r.pos += 4
        else:
            break

        if name in out:
            if not isinstance(out[name], list):
                out[name] = [out[name]]
            out[name].append(value)
        else:
            out[name] = value
    return out


def _as_list(value):
    """把单值 / 列表 / 内嵌 entries 统一成列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_master_list(data):
    """解析 /api/monthlyranking → [ {monthlyRankingId, name, startAt, endAt, assetBundleName, ...} ]"""
    root = _decode_message(data, MASTER_LIST_SCHEMA)
    entries = _as_list(root.get('entries'))
    return entries


def parse_ranking(data):
    """解析月榜 ranking 响应 → { 'top': [用户...], 'border': [用户...] }。

    每个用户: {name, rank, point, userId, introduction, degreeId}
    """
    root = _decode_message(data, RANKING_RESPONSE_SCHEMA)
    result = {}
    for key, field in (('top', 'monthlyRankingPointTopUsers'),
                       ('border', 'monthlyRankingPointBorderUsers')):
        container = root.get(field)
        users = []
        if isinstance(container, dict):
            users = _as_list(container.get('entries'))
        elif isinstance(container, list):
            for c in container:
                if isinstance(c, dict):
                    users.extend(_as_list(c.get('entries')))
        result[key] = users
    return result
