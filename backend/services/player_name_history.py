"""Passive name changes; each consecutive use of a name has its own row."""
from sqlalchemy import select
from sqlalchemy.schema import CreateTable, CreateIndex
from models import db, PlayerNameHistory
from services.timeutil import now_ms


def init_name_history():
    table = PlayerNameHistory.__table__
    with db.engine.connect() as connection:
        # Serialize schema inspection/migration across web and scheduler processes.
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            columns = connection.exec_driver_sql(
                'PRAGMA table_info(player_name_history)').fetchall()
            legacy = columns and 'id' not in {row[1] for row in columns}
            if legacy:
                connection.exec_driver_sql(
                    'ALTER TABLE player_name_history RENAME TO player_name_history_legacy')
            connection.execute(CreateTable(table, if_not_exists=True))
            if legacy:
                # The old schema lost first-seen times and repeated name changes.
                # Keep its observations without inventing first-seen timestamps.
                connection.exec_driver_sql("""
                    INSERT INTO player_name_history (uid, name, first_seen, last_observed)
                    SELECT uid, name, NULL, last_seen FROM player_name_history_legacy
                    ORDER BY last_seen, uid, name
                """)
            for index in table.indexes:
                connection.execute(CreateIndex(index, if_not_exists=True))
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def record_names(users, observed_at=None):
    timestamp = now_ms() if observed_at is None else int(observed_at)
    rows = {}
    for user in users:
        uid, name = user.get('uid'), user.get('name')
        if uid is None or not str(uid).isdigit() or int(uid) <= 0:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        rows[str(int(uid))] = name
    if not rows:
        return
    table = PlayerNameHistory.__table__
    with db.engine.connect() as connection:
        # Compare and append under one SQLite write lock, including other processes.
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            for uid, name in rows.items():
                latest = connection.execute(select(table).where(table.c.uid == uid)
                                            .order_by(table.c.id.desc()).limit(1)).mappings().first()
                if latest and timestamp < latest['last_observed']:
                    continue
                if latest and latest['name'] == name:
                    connection.execute(table.update().where(table.c.id == latest['id'])
                                       .values(last_observed=timestamp))
                else:
                    connection.execute(table.insert().values(
                        uid=uid, name=name, first_seen=timestamp, last_observed=timestamp))
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def get_name_history(uid):
    table = PlayerNameHistory.__table__
    with db.engine.connect() as connection:
        rows = connection.execute(
            select(table.c.id, table.c.name, table.c.first_seen)
            .where(table.c.uid == str(int(uid)))
            .order_by(table.c.id.desc())
        )
        return [dict(row._mapping) for row in rows]
