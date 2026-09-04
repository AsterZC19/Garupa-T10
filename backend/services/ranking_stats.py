"""Shared chart sampling and hourly statistics for event and monthly rankings."""

def row_timestamp(row):
    return row.timestamp


def row_pt(row):
    return row.pt


def _downsample_points(points, max_points):
    """Downsample a sorted list of {t, pt} dicts to at most max_points, preserving peaks."""
    if len(points) <= max_points:
        return points

    result = [points[0]]
    remaining_slots = max_points - 2  # reserve for first and last
    if remaining_slots <= 0:
        result.append(points[-1])
        return result

    inner = points[1:-1]
    bucket_size = max(1, len(inner) // remaining_slots)

    for i in range(0, len(inner), bucket_size):
        bucket = inner[i:i + bucket_size]
        # pick the point with the highest pt in each bucket to preserve peaks
        result.append(max(bucket, key=lambda p: p['pt']))

    result.append(points[-1])
    return result


def find_closest_point(scores, target_ts):
    if not scores:
        return None
    return min(scores, key=lambda score: abs(row_timestamp(score) - target_ts))


def find_last_point_before(scores, target_ts):
    relevant_scores = [score for score in scores if row_timestamp(score) < target_ts]
    return relevant_scores[-1] if relevant_scores else None


def calculate_hourly_stats(player_history, start_ts, end_ts, is_new):
    hourly_speed = 0
    run_count = 0
    average_pt = 0

    if player_history and not is_new:
        start_point = find_closest_point(player_history, start_ts)
        end_point = find_closest_point(player_history, end_ts)

        if start_point and end_point and row_timestamp(start_point) < row_timestamp(end_point):
            time_diff_h = (row_timestamp(end_point) - row_timestamp(start_point)) / 3600000
            if time_diff_h > 0:
                speed = (row_pt(end_point) - row_pt(start_point)) / time_diff_h
                hourly_speed = round(speed) if speed > 0 else 0

        scores_in_hour = [record for record in player_history if start_ts <= row_timestamp(record) < end_ts]
        if scores_in_hour:
            last_score_before_hour = find_last_point_before(player_history, start_ts)
            last_pt = row_pt(last_score_before_hour) if last_score_before_hour else row_pt(scores_in_hour[0])

            for record in scores_in_hour:
                if row_pt(record) > last_pt:
                    run_count += 1
                last_pt = row_pt(record)

        if run_count > 0:
            average_pt = hourly_speed // run_count
    return hourly_speed, run_count, average_pt
