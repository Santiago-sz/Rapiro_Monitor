from cloud_processor.db import get_pool
from cloud_processor.config import MIN_SAMPLES_TO_LEARN, ANOMALY_THRESHOLD


def get_pattern(hour: int) -> dict | None:
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT avg_motion_freq, avg_light_percent, motion_std, light_std, sample_count "
                "FROM hourly_patterns WHERE hour_of_day = %s",
                (hour,)
            )
            row = cur.fetchone()
        if row:
            return {
                "avg_motion_freq": row[0],
                "avg_light_percent": row[1],
                "motion_std": row[2],
                "light_std": row[3],
                "sample_count": row[4],
            }
        return None
    finally:
        pool.putconn(conn)


def update_pattern(hour: int, motion_value: float, light_value: float) -> None:
    """Incremental mean + exponential-decay std update for the given hour slot."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT avg_motion_freq, avg_light_percent, motion_std, light_std, sample_count "
                "FROM hourly_patterns WHERE hour_of_day = %s FOR UPDATE",
                (hour,)
            )
            row = cur.fetchone()
            if row:
                n = row[4] + 1
                new_avg_m = row[0] + (motion_value - row[0]) / n
                new_avg_l = row[1] + (light_value - row[1]) / n
                # Exponential moving std — fast adaptation, smooth noise
                new_std_m = max(row[2] * 0.95 + abs(motion_value - new_avg_m) * 0.05, 0.01)
                new_std_l = max(row[3] * 0.95 + abs(light_value - new_avg_l) * 0.05, 0.05)
                cur.execute(
                    """UPDATE hourly_patterns
                       SET avg_motion_freq = %s, avg_light_percent = %s,
                           motion_std = %s, light_std = %s,
                           sample_count = %s, updated_at = NOW()
                       WHERE hour_of_day = %s""",
                    (new_avg_m, new_avg_l, new_std_m, new_std_l, n, hour),
                )
            else:
                cur.execute(
                    """INSERT INTO hourly_patterns
                       (hour_of_day, avg_motion_freq, avg_light_percent,
                        motion_std, light_std, sample_count, updated_at)
                       VALUES (%s, %s, %s, 0.1, 0.05, 1, NOW())""",
                    (hour, motion_value, light_value),
                )
        conn.commit()
    finally:
        pool.putconn(conn)


def compute_anomaly(hour: int, motion_value: float, light_value: float) -> tuple[float, str]:
    """
    Returns (anomaly_score, alert_level).
    Needs at least MIN_SAMPLES_TO_LEARN observations before scoring.
    alert_level: 'none' | 'info' | 'warning' | 'critical'
    """
    pattern = get_pattern(hour)
    if pattern is None or pattern["sample_count"] < MIN_SAMPLES_TO_LEARN:
        return 0.0, "none"

    motion_z = abs(motion_value - pattern["avg_motion_freq"]) / pattern["motion_std"]
    light_z = abs(light_value - pattern["avg_light_percent"]) / pattern["light_std"]
    score = (motion_z + light_z) / 2.0

    if score < ANOMALY_THRESHOLD:
        level = "none"
    elif score < ANOMALY_THRESHOLD * 1.5:
        level = "info"
    elif score < ANOMALY_THRESHOLD * 2.5:
        level = "warning"
    else:
        level = "critical"

    return round(score, 3), level
