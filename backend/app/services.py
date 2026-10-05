"""缫丝盆门槛：标成已缫完须最近一次汤温落在 38～42℃；同盆连登汤温须满最小间隔。"""

import math
from datetime import datetime, timezone

from app.models import Basin, BathReading

MIN_TEMP = 38.0
MAX_TEMP = 42.0

SETTING_MIN_INTERVAL = "min_interval_minutes"
DEFAULT_MIN_INTERVAL_MINUTES = 5
MIN_INTERVAL_FLOOR = 5


class RuleError(ValueError):
    pass


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def latest_reading(basin: Basin) -> BathReading | None:
    if not basin.readings:
        return None
    return max(basin.readings, key=lambda r: r.taken_at)


def latest_temp(basin: Basin) -> float | None:
    latest = latest_reading(basin)
    if latest is None:
        return None
    return latest.water_temp_c


def parse_min_interval_minutes(raw) -> int:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise RuleError("间隔分钟必须是数字")
    if not math.isfinite(value) or not value.is_integer():
        raise RuleError("间隔分钟须为整数")
    minutes = int(value)
    if minutes < MIN_INTERVAL_FLOOR:
        raise RuleError(f"最小间隔至少 {MIN_INTERVAL_FLOOR} 分钟")
    return minutes


def wait_seconds(basin: Basin, now: datetime, min_minutes: int) -> int:
    """距可再次登记还剩多少秒；可登则为 0。"""
    latest = latest_reading(basin)
    if latest is None:
        return 0
    elapsed = (now - _as_utc(latest.taken_at)).total_seconds()
    return max(0, math.ceil(min_minutes * 60 - elapsed))


def assert_can_add_reading(basin: Basin, now: datetime, min_minutes: int) -> None:
    remain = wait_seconds(basin, now, min_minutes)
    if remain > 0:
        raise RuleError(
            f"距上次登记不足 {min_minutes} 分钟，还需约 {remain} 秒，请稍后再登"
        )


def assert_can_set_status(basin: Basin, new_status: str) -> None:
    allowed = {Basin.STATUS_SOAKING, Basin.STATUS_REELING, Basin.STATUS_REELED}
    if new_status not in allowed:
        raise RuleError(f"无效状态：{new_status}")
    if new_status != Basin.STATUS_REELED:
        return
    temp = latest_temp(basin)
    if temp is None:
        raise RuleError("该盆尚无汤温记录，不能标已缫完")
    if temp < MIN_TEMP or temp > MAX_TEMP:
        raise RuleError(
            f"最近汤温 {temp}℃ 不在 {MIN_TEMP:.0f}～{MAX_TEMP:.0f}℃，不能标已缫完"
        )
