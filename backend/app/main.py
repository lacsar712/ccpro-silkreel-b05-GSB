import math

from quart import Quart, g, jsonify, request
from quart.helpers import make_response

from app.db import SessionLocal
from app.models import Basin, utcnow
from app.repositories import BasinRepo, SettingRepo, UserRepo
from app.security import make_token, parse_token, verify_password
from app.services import (
    DEFAULT_MIN_INTERVAL_MINUTES,
    SETTING_MIN_INTERVAL,
    RuleError,
    assert_can_add_reading,
    assert_can_set_status,
    latest_reading,
    latest_temp,
    parse_min_interval_minutes,
    wait_seconds,
)

app = Quart(__name__)


def _bearer() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None


@app.before_request
async def load_user():
    g.user = None
    token = _bearer()
    if not token:
        return
    username = parse_token(token)
    if not username:
        return
    async with SessionLocal() as session:
        g.user = await UserRepo(session).by_username(username)


def require_user():
    if g.user is None:
        return jsonify({"detail": "未登录"}), 401
    return None


def require_admin():
    denied = require_user()
    if denied:
        return denied
    if g.user.role != "admin":
        return jsonify({"detail": "仅管理员可修改汤温间隔"}), 403
    return None


async def _min_interval_minutes(session) -> int:
    raw = await SettingRepo(session).get_value(SETTING_MIN_INTERVAL)
    if raw is None:
        return DEFAULT_MIN_INTERVAL_MINUTES
    try:
        return parse_min_interval_minutes(raw)
    except RuleError:
        return DEFAULT_MIN_INTERVAL_MINUTES


@app.route("/api/health")
async def health():
    return {"status": "ok", "service": "SilkReel"}


@app.route("/api/auth/login", methods=["POST"])
async def login():
    body = await request.get_json(force=True)
    username = (body or {}).get("username", "")
    password = (body or {}).get("password", "")
    async with SessionLocal() as session:
        user = await UserRepo(session).by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            return jsonify({"detail": "用户名或密码错误"}), 401
        return {
            "access_token": make_token(user.username),
            "user": {"username": user.username, "role": user.role},
        }


@app.route("/api/auth/me")
async def me():
    denied = require_user()
    if denied:
        return denied
    return {"username": g.user.username, "role": g.user.role}


def _basin_json(basin: Basin) -> dict:
    return {
        "id": basin.id,
        "code": basin.code,
        "status": basin.status,
        "ringIndex": basin.ring_index,
        "latestTempC": latest_temp(basin),
        "readingCount": len(basin.readings or []),
    }


@app.route("/api/board")
async def board():
    denied = require_user()
    if denied:
        return denied
    async with SessionLocal() as session:
        mill = await BasinRepo(session).board()
        if mill is None:
            return jsonify({"detail": "尚无缫丝坞"}), 404
        basins = sorted(mill.basins, key=lambda b: b.ring_index)
        return {
            "filature": mill.name,
            "riverside": mill.riverside,
            "basins": [_basin_json(b) for b in basins],
        }


@app.route("/api/settings/interval")
async def get_interval():
    denied = require_user()
    if denied:
        return denied
    async with SessionLocal() as session:
        minutes = await _min_interval_minutes(session)
        mill = await BasinRepo(session).board()
        if mill is None:
            return jsonify({"detail": "尚无缫丝坞"}), 404
        now = utcnow()
        basins = []
        for b in sorted(mill.basins, key=lambda x: x.ring_index):
            latest = latest_reading(b)
            basins.append(
                {
                    "id": b.id,
                    "code": b.code,
                    "lastTakenAt": latest.taken_at.isoformat() if latest else None,
                    "waitSeconds": wait_seconds(b, now, minutes),
                }
            )
        return {"minIntervalMinutes": minutes, "basins": basins}


@app.route("/api/settings/interval", methods=["PUT"])
async def put_interval():
    denied = require_admin()
    if denied:
        return denied
    body = await request.get_json(force=True)
    try:
        minutes = parse_min_interval_minutes((body or {}).get("minIntervalMinutes"))
    except RuleError as exc:
        return jsonify({"detail": str(exc)}), 400
    async with SessionLocal() as session:
        await SettingRepo(session).set_value(SETTING_MIN_INTERVAL, str(minutes))
    return {"minIntervalMinutes": minutes}


@app.route("/api/basins/<int:basin_id>/readings", methods=["POST"])
async def add_reading(basin_id: int):
    denied = require_user()
    if denied:
        return denied
    body = await request.get_json(force=True)
    try:
        temp = float((body or {}).get("waterTempC"))
    except (TypeError, ValueError):
        return jsonify({"detail": "汤温必须是数字"}), 400
    if not math.isfinite(temp):
        return jsonify({"detail": "汤温必须是数字"}), 400
    async with SessionLocal() as session:
        repo = BasinRepo(session)
        basin = await repo.get(basin_id)
        if basin is None:
            return jsonify({"detail": "盆不存在"}), 404
        minutes = await _min_interval_minutes(session)
        try:
            assert_can_add_reading(basin, utcnow(), minutes)
        except RuleError as exc:
            return jsonify({"detail": str(exc)}), 400
        await repo.add_reading(basin, temp, g.user.username)
        basin = await repo.get(basin_id)
        return _basin_json(basin)


@app.route("/api/basins/<int:basin_id>/status", methods=["POST"])
async def set_status(basin_id: int):
    denied = require_user()
    if denied:
        return denied
    body = await request.get_json(force=True)
    status = (body or {}).get("status", "")
    async with SessionLocal() as session:
        repo = BasinRepo(session)
        basin = await repo.get(basin_id)
        if basin is None:
            return jsonify({"detail": "盆不存在"}), 404
        try:
            assert_can_set_status(basin, status)
        except RuleError as exc:
            return jsonify({"detail": str(exc)}), 400
        await repo.save_status(basin, status)
        basin = await repo.get(basin_id)
        return _basin_json(basin)
