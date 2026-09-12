"""Passive name observations only; never fetch player profiles here."""
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.schema import CreateTable
from models import db, PlayerNameHistory
from services.timeutil import now_ms


def init_name_history():
    # Web and scheduler import app concurrently. A separate existence check
    # (checkfirst=True) races; let SQLite handle this in the CREATE statement.
    with db.engine.begin() as connection:
        connection.execute(CreateTable(PlayerNameHistory.__table__, if_not_exists=True))


def record_names(users, observed_at=None):
    timestamp = now_ms() if observed_at is None else int(observed_at)
    rows = {}
    for user in users:
        uid, name = user.get('uid'), user.get('name')
        if uid is None or not str(uid).isdigit() or int(uid) <= 0:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        uid = str(int(uid))
        rows[(uid, name)] = dict(uid=uid, name=name, last_seen=timestamp)
    if not rows:
        return
    table = PlayerNameHistory.__table__
    statement = insert(table)
    statement = statement.on_conflict_do_update(
        index_elements=['uid', 'name'],
        set_={'last_seen': func.max(table.c.last_seen, statement.excluded.last_seen)},
    )
    with db.engine.begin() as connection:
        connection.execute(statement, list(rows.values()))


def get_name_history(uid):
    table = PlayerNameHistory.__table__
    with db.engine.connect() as connection:
        rows = connection.execute(
            select(table.c.name, table.c.last_seen)
            .where(table.c.uid == str(int(uid)))
            .order_by(table.c.last_seen.desc(), table.c.name.asc())
        )
        return [dict(row._mapping) for row in rows]
