"""月榜诊断脚本：验证 GarupaSpeedTracker 后端（GARUPA_TRACKER_BASE）可拉取月榜数据。

用法：
    conda activate App
    python test_monthly.py                # 打印全部月榜期 + 当前期 top 榜单
    python test_monthly.py <monthly_id>   # 指定月榜期

若报 TrackerError，请先在 backend/.env 配置 GARUPA_TRACKER_BASE 指向已部署的
GarupaSpeedTracker 后端。
"""
import sys

from services import tracker_client, monthly_ingestion
from services import monthly_repository as repo


def main():
    from app import app
    from models import db
    with app.app_context():
        db.create_all()

        print(f"== tracker 后端: {tracker_client.GARUPA_TRACKER_BASE} ==")
        print("\n== info（月榜期列表）==")
        info = tracker_client.get_monthly_info(force=True)
        print(f"共 {len(info or {})} 期月榜")
        cur = repo.get_current_or_latest_monthly()
        mid = int(sys.argv[1]) if len(sys.argv) > 1 else (cur.monthly_id if cur else None)
        if not mid:
            print("无月榜期，退出")
            return
        cur_meta = info.get(str(mid), {}) if info else {}
        name_arr = cur_meta.get('monthlyRankingName') or []
        print(f"目标月榜: id={mid} name={(name_arr[0] if name_arr else cur_meta.get('name'))}")

        print(f"\n== top 快照（mid={mid}）==")
        snapshot = tracker_client.get_monthly_top(mid, force=True)
        points = snapshot.get('points') or []
        users = snapshot.get('users') or []
        print(f"历史点 {len(points)} 个，玩家 {len(users)} 名")
        latest = {}
        for p in points:
            uid = str(p.get('uid'))
            ts = int(p.get('time') or p.get('timestamp') or 0)
            val = int(p.get('value') or 0)
            if uid not in latest or ts > latest[uid][0]:
                latest[uid] = (ts, val)
        ranked = sorted(latest.items(), key=lambda kv: kv[1][1], reverse=True)
        name_map = {str(u.get('uid')): u.get('name') for u in users}
        for uid, (ts, pt) in ranked[:10]:
            print(f"  uid={uid} pt={pt} name={name_map.get(uid)}")

        print("\n== 落库 ==")
        inserted = monthly_ingestion.refresh_monthly_top(mid)
        print(f"本次新增历史点: {inserted}")
        print(f"库里已有历史点: {repo.get_monthly_last_stored_ts(mid)}")


if __name__ == '__main__':
    main()
