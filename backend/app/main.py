import math
from datetime import timezone

from quart import Quart, g, jsonify, request
from quart.helpers import make_response

from app.db import SessionLocal
from app.models import Basin
from app.repositories import BasinRepo, SettingsRepo, UserRepo
from app.security import make_token, parse_token, verify_password
from app.services import (
    RuleError,
    assert_can_add_reading,
    assert_can_set_status,
    effective_min_interval,
    latest_reading,
    parse_min_interval,
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
        return jsonify({"detail": "仅管理员可调整汤温间隔"}), 403
    return None


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
    latest = latest_reading(basin)
    taken_at = None
    if latest is not None:
        taken_at = latest.taken_at
        if taken_at.tzinfo is None:
            taken_at = taken_at.replace(tzinfo=timezone.utc)
    return {
        "id": basin.id,
        "code": basin.code,
        "status": basin.status,
        "ringIndex": basin.ring_index,
        "latestTempC": latest.water_temp_c if latest else None,
        "latestTakenAt": taken_at.isoformat() if taken_at else None,
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


@app.route("/api/settings/reading-interval")
async def get_reading_interval():
    denied = require_user()
    if denied:
        return denied
    async with SessionLocal() as session:
        raw = await SettingsRepo(session).min_interval_raw()
    return {"minIntervalMinutes": effective_min_interval(raw)}


@app.route("/api/settings/reading-interval", methods=["PUT"])
async def put_reading_interval():
    denied = require_admin()
    if denied:
        return denied
    body = await request.get_json(force=True)
    try:
        minutes = parse_min_interval((body or {}).get("minIntervalMinutes"))
    except RuleError as exc:
        return jsonify({"detail": str(exc)}), 400
    async with SessionLocal() as session:
        await SettingsRepo(session).save_min_interval(minutes)
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
        raw = await SettingsRepo(session).min_interval_raw()
        try:
            assert_can_add_reading(basin, effective_min_interval(raw))
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
