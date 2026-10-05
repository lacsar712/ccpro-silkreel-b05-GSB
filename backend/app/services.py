"""缫丝盆门槛：标成已缫完须最近一次汤温落在 38～42℃；
同一盆两次汤温登记须隔满管理员设定的最小间隔分钟。"""

from datetime import datetime, timedelta, timezone

from app.models import DEFAULT_MIN_INTERVAL_MINUTES, Basin, BathReading

MIN_TEMP = 38.0
MAX_TEMP = 42.0

# 最小间隔分钟的下限：管理员也只能设到 5 或以上
MIN_INTERVAL_FLOOR = 5


class RuleError(ValueError):
    pass


def latest_reading(basin: Basin) -> BathReading | None:
    if not basin.readings:
        return None
    return max(basin.readings, key=lambda r: r.taken_at)


def latest_temp(basin: Basin) -> float | None:
    latest = latest_reading(basin)
    return latest.water_temp_c if latest else None


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


def parse_min_interval(raw) -> int:
    """管理员提交的间隔分钟：必须是整数且不少于下限。"""
    if isinstance(raw, bool):
        raise RuleError("间隔分钟必须是整数")
    if isinstance(raw, int):
        minutes = raw
    elif isinstance(raw, float) and raw.is_integer():
        minutes = int(raw)
    elif isinstance(raw, str):
        try:
            minutes = int(raw.strip())
        except ValueError:
            raise RuleError("间隔分钟必须是整数") from None
    else:
        raise RuleError("间隔分钟必须是整数")
    if minutes < MIN_INTERVAL_FLOOR:
        raise RuleError(f"最小间隔不能少于 {MIN_INTERVAL_FLOOR} 分钟")
    return minutes


def effective_min_interval(stored: str | None) -> int:
    """库里没存或存坏了时回落到默认最小间隔。"""
    try:
        minutes = int(str(stored).strip())
    except (TypeError, ValueError):
        return DEFAULT_MIN_INTERVAL_MINUTES
    if minutes < MIN_INTERVAL_FLOOR:
        return DEFAULT_MIN_INTERVAL_MINUTES
    return minutes


def assert_can_add_reading(
    basin: Basin, min_interval_minutes: int, now: datetime | None = None
) -> None:
    """同一盆刚登记过汤温，间隔未满再登必须挡下（不入库）。"""
    latest = latest_reading(basin)
    if latest is None:
        return
    taken_at = latest.taken_at
    if taken_at.tzinfo is None:
        taken_at = taken_at.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now - taken_at < timedelta(minutes=min_interval_minutes):
        raise RuleError(
            f"同一盆两次登记须间隔至少 {min_interval_minutes} 分钟，"
            "距上次登记还未满，本次未入库"
        )
