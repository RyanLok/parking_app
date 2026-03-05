"""
共享停车抢单 API 服务
隔离策略：用手机号（mobile_b64）作为用户唯一 key
- 同一手机号无论从哪个浏览器登录，都操作同一个 Bot
- 配置持久化到 data/{mobile_hash}.json，重启不丢
- session_id 只是临时连接标识，登录后绑定到手机号
"""
import base64
import hashlib
import json
import logging
import os
import time
import threading
from pathlib import Path
from typing import Dict, Tuple, Optional, Union

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from api_simulator import get_park_list, get_city_list, get_plate_list, do_login, send_sms_code, login_with_sms, cancel_order
from bot import ParkingBot

app = FastAPI(title="Auto Parking API")

# CORS：环境变量 CORS_ORIGINS 覆盖，默认含本地开发 + 常见 Vercel 域名
_DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173,https://parking-app-brown-two.vercel.app"
CORS_ORIGINS = [o.strip() for o in (os.environ.get("CORS_ORIGINS") or _DEFAULT_CORS).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# 禁止任何缓存，防止 nginx/CDN 缓存动态 API 响应导致返回过时数据
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(NoCacheMiddleware)

# ========== 数据目录 ==========
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ========== 注册表 ==========
# 两层映射：session_id → mobile_key, mobile_key → (Bot, last_ts)
_session_to_mobile: Dict[str, str] = {}
_bots: Dict[str, Tuple[ParkingBot, float]] = {}
_lock = threading.Lock()
SESSION_TIMEOUT = 24 * 3600
_last_cleanup_ts: float = 0.0
_CLEANUP_INTERVAL = 300  # 5 分钟清理一次
_SESSIONS_FILE = DATA_DIR / "sessions.json"
logger = logging.getLogger("parking")


def _load_sessions() -> None:
    """启动时恢复 session 映射，刷新/重启后用户免重登"""
    if not _SESSIONS_FILE.exists():
        return
    try:
        data = json.loads(_SESSIONS_FILE.read_text())
        if isinstance(data, dict):
            _session_to_mobile.update(data)
            logger.info("恢复 %d 个 session 映射", len(data))
    except Exception as exc:
        logger.warning("加载 sessions 失败: %s", exc)


def _save_sessions() -> None:
    """持久化 session 映射（原子写入，防止崩溃时写出半截文件）"""
    try:
        with _lock:
            data = dict(_session_to_mobile)
        tmp = _SESSIONS_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(_SESSIONS_FILE)
    except Exception as exc:
        logger.warning("保存 sessions 失败: %s", exc)


# 启动时恢复
_load_sessions()


def _config_path(mobile_key: str) -> Path:
    """用户配置文件路径"""
    safe = hashlib.sha256(mobile_key.encode()).hexdigest()[:16]
    return DATA_DIR / f"{safe}.json"


def _save_config(mobile_key: str, config: dict) -> None:
    """持久化配置到磁盘（原子写入）"""
    try:
        p = _config_path(mobile_key)
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2))
        tmp.replace(p)
    except Exception as exc:
        logger.warning("保存配置失败 [%s]: %s", mobile_key[:8], exc)


def _logs_path(mobile_key: str) -> Path:
    """用户日志文件路径"""
    safe = hashlib.sha256(mobile_key.encode()).hexdigest()[:16]
    return DATA_DIR / f"{safe}.logs.json"


def _save_logs(mobile_key: str, logs: list) -> None:
    """持久化日志到磁盘（只保留最近 200 条）"""
    try:
        p = _logs_path(mobile_key)
        p.write_text(json.dumps(logs[-200:], ensure_ascii=False))
    except Exception:
        pass


def _load_logs(mobile_key: str) -> list:
    """从磁盘加载日志"""
    p = _logs_path(mobile_key)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            if isinstance(data, list):
                return data[-200:]
        except Exception:
            pass
    return []


def _load_config(mobile_key: str) -> Optional[dict]:
    """从磁盘加载配置"""
    p = _config_path(mobile_key)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return None


def _cleanup_stale() -> None:
    """清理超时未活跃的会话（节流：至多每 5 分钟执行一次）"""
    global _last_cleanup_ts
    now = time.time()
    with _lock:
        if now - _last_cleanup_ts < _CLEANUP_INTERVAL:
            return
        _last_cleanup_ts = now

        stale_sessions = []
        stale_mobiles = []
        for sid, mk in list(_session_to_mobile.items()):
            if mk in _bots:
                _, ts = _bots[mk]
                if now - ts > SESSION_TIMEOUT:
                    stale_sessions.append(sid)
            # 如果 mobile_key 不在 _bots 中，可能是还没被加载，不要误删
            # else:
            #     stale_sessions.append(sid)
        for sid in stale_sessions:
            _session_to_mobile.pop(sid, None)
        for mk, (bot, ts) in list(_bots.items()):
            if now - ts > SESSION_TIMEOUT and not bot.is_running:
                stale_mobiles.append(mk)
        for mk in stale_mobiles:
            del _bots[mk]
    if stale_sessions or stale_mobiles:
        _save_sessions()
        logger.info("清理过期会话: %d 个 session, %d 个 bot", len(stale_sessions), len(stale_mobiles))


def _get_bot_by_mobile(mobile_key: str) -> ParkingBot:
    """根据手机号获取或创建 Bot（已登录用户）"""
    now = time.time()
    with _lock:
        if mobile_key in _bots:
            bot, _ = _bots[mobile_key]
            _bots[mobile_key] = (bot, now)
            return bot

    # 磁盘 I/O 在锁外执行，避免阻塞其他请求
    saved = _load_config(mobile_key)
    bot = ParkingBot()
    if saved:
        bot.config.update(saved)
        if "token" in saved and saved["token"]:
            bot.token = saved["token"]

    # 注册持久化回调：bot 运行中 token 变更时自动存盘
    _mk = mobile_key
    def _persist_on_token_change(b: ParkingBot) -> None:
        _save_config(_mk, b.config)
    bot._on_token_change = _persist_on_token_change

    # 注册日志持久化回调
    def _persist_logs(b: ParkingBot) -> None:
        _save_logs(_mk, b.logs)
    bot._on_log = _persist_logs

    # 从磁盘恢复日志
    saved_logs = _load_logs(mobile_key)
    if saved_logs:
        bot.logs = saved_logs

    with _lock:
        # double-check：并发时可能另一个线程已经创建了
        if mobile_key in _bots:
            existing, _ = _bots[mobile_key]
            _bots[mobile_key] = (existing, now)
            return existing
        _bots[mobile_key] = (bot, now)
        return bot


def _get_session_id(x_session_id: Optional[str] = Header(None, alias="X-Session-Id")) -> str:
    """提取并校验 session ID"""
    if not x_session_id or not x_session_id.strip():
        raise HTTPException(status_code=400, detail="缺少 X-Session-Id，请刷新页面重试")
    return x_session_id.strip()


def get_bot(session_id: str = Depends(_get_session_id)) -> ParkingBot:
    """
    严格按 session_id 返回对应用户的 Bot，确保多用户隔离。
    - 已登录：session → mobile → 该用户唯一 Bot
    - 未登录：临时 bot，互不影响
    """
    _cleanup_stale()
    with _lock:
        mobile_key = _session_to_mobile.get(session_id)
    
    # 内存中没找到，尝试从磁盘重新加载（服务重启后内存可能与磁盘不同步）
    if not mobile_key:
        try:
            if _SESSIONS_FILE.exists():
                disk_data = json.loads(_SESSIONS_FILE.read_text())
                if isinstance(disk_data, dict) and session_id in disk_data:
                    mobile_key = disk_data[session_id]
                    with _lock:
                        _session_to_mobile[session_id] = mobile_key
                    logger.info("从磁盘恢复 session 映射: %s -> %s", session_id[:8], mobile_key[:8])
        except Exception as exc:
            logger.warning("回读 sessions.json 失败: %s", exc)
    
    if mobile_key:
        return _get_bot_by_mobile(mobile_key)
    # 未登录的 session，创建临时 bot
    now = time.time()
    with _lock:
        temp_key = f"_tmp_{session_id}"
        if temp_key in _bots:
            bot, _ = _bots[temp_key]
            _bots[temp_key] = (bot, now)
            return bot
        bot = ParkingBot()
        _bots[temp_key] = (bot, now)
        return bot


# ========== Pydantic Models ==========
class LoginModel(BaseModel):
    """密码登录请求"""
    mobile: str
    password: str
    lng: Optional[str] = None
    lat: Optional[str] = None


class SmsSendModel(BaseModel):
    """发送验证码请求"""
    mobile: str
    lng: Optional[str] = None
    lat: Optional[str] = None


class SmsLoginModel(BaseModel):
    """验证码登录请求"""
    mobile: str
    sms_code: str
    lng: Optional[str] = None
    lat: Optional[str] = None


class ConfigModel(BaseModel):
    """配置项模型"""
    mobile: str
    password_md5: str = ""
    lng: str
    lat: str
    park_id: Union[int, str]
    city_id: Union[int, str]
    plate_id: Union[int, str]
    expect_leave_time: str
    start_time: str
    end_time: str
    poll_interval: int = 5
    safe_cancel_advance: int = 10
    city_name: Optional[str] = None
    park_name: Optional[str] = None
    plate_no: Optional[str] = None
    token: Optional[str] = None


# ========== API Routes ==========
@app.post("/api/auth/login")
def auth_login(body: LoginModel, session_id: str = Depends(_get_session_id)):
    """
    登录：验证通过后，将 session 绑定到该手机号的 Bot
    - 同一手机号已有 Bot 在跑 → 直接复用，不会重复创建
    - 配置从磁盘恢复
    """
    mobile = (body.mobile or "").strip()
    password = (body.password or "").strip()
    if not mobile or not password:
        raise HTTPException(status_code=400, detail="请输入手机号和密码")

    mobile_b64 = base64.b64encode(mobile.encode("utf-8")).decode("utf-8")
    password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest().upper()

    # 获取或创建此手机号的 bot
    bot = _get_bot_by_mobile(mobile_b64)

    lng = body.lng or bot.config.get("lng") or "113.430183"
    lat = body.lat or bot.config.get("lat") or "23.181934"

    try:
        res = do_login(mobile_b64, password_md5, lng, lat)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"登录服务暂时不可用：{str(e)[:80]}")

    if not isinstance(res, dict):
        raise HTTPException(status_code=502, detail="登录服务返回格式异常")

    result = res.get("result", {}) or {}
    token = result.get("token") if isinstance(result, dict) else None
    if not token:
        msg = res.get("desc", "登录失败") or "登录失败"
        raise HTTPException(status_code=401, detail=str(msg))

    # 登录成功：更新 bot 凭据
    bot.config["mobile"] = mobile_b64
    bot.config["password_md5"] = password_md5
    bot.config["lng"] = lng
    bot.config["lat"] = lat
    bot.config["token"] = token
    bot.token = token

    # 绑定 session → mobile
    with _lock:
        old_tmp = f"_tmp_{session_id}"
        _bots.pop(old_tmp, None)
        _session_to_mobile[session_id] = mobile_b64
    _save_sessions()
    _save_config(mobile_b64, bot.config)

    return {
        "success": True,
        "is_running": bot.is_running,
        "status": bot.status,
    }


@app.post("/api/auth/sms/send")
def auth_sms_send(body: SmsSendModel, session_id: str = Depends(_get_session_id)):
    """
    发送验证码到手机号
    """
    mobile = (body.mobile or "").strip()
    if not mobile or len(mobile) != 11:
        raise HTTPException(status_code=400, detail="请输入正确的11位手机号")

    bot = get_bot(session_id)
    lng = body.lng or bot.config.get("lng") or "113.430183"
    lat = body.lat or bot.config.get("lat") or "23.181934"

    try:
        res = send_sms_code(mobile, lng, lat)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"发送验证码失败：{str(e)[:80]}")

    if res.get("code") != 200:
        msg = res.get("desc", "发送失败") or "发送失败"
        raise HTTPException(status_code=400, detail=str(msg))

    return {"success": True, "message": "验证码已发送"}


@app.post("/api/auth/sms/login")
def auth_sms_login(body: SmsLoginModel, session_id: str = Depends(_get_session_id)):
    """
    验证码登录：验证通过后绑定 session，与密码登录效果一致
    """
    mobile = (body.mobile or "").strip()
    sms_code = (body.sms_code or "").strip()
    if not mobile or len(mobile) != 11:
        raise HTTPException(status_code=400, detail="请输入正确的11位手机号")
    if not sms_code or len(sms_code) != 6:
        raise HTTPException(status_code=400, detail="请输入6位验证码")

    mobile_b64 = base64.b64encode(mobile.encode("utf-8")).decode("utf-8")
    bot = _get_bot_by_mobile(mobile_b64)
    lng = body.lng or bot.config.get("lng") or "113.430183"
    lat = body.lat or bot.config.get("lat") or "23.181934"

    try:
        res = login_with_sms(mobile_b64, sms_code, lng, lat)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"登录服务暂时不可用：{str(e)[:80]}")

    if not isinstance(res, dict):
        raise HTTPException(status_code=502, detail="登录服务返回格式异常")

    result = res.get("result", {}) or {}
    token = result.get("token") if isinstance(result, dict) else None
    if not token:
        msg = res.get("desc", "验证码错误或已过期") or "验证码错误或已过期"
        logger.warning("验证码登录失败 mobile=%s res=%s", mobile[:3] + "****", res)
        raise HTTPException(status_code=401, detail=str(msg))

    # 验证码登录：无密码，仅存 token，token 过期需重新验证码登录
    bot.config["mobile"] = mobile_b64
    bot.config["password_md5"] = ""
    bot.config["lng"] = lng
    bot.config["lat"] = lat
    bot.config["token"] = token
    bot.token = token

    with _lock:
        old_tmp = f"_tmp_{session_id}"
        _bots.pop(old_tmp, None)
        _session_to_mobile[session_id] = mobile_b64
    _save_sessions()
    _save_config(mobile_b64, bot.config)

    return {
        "success": True,
        "is_running": bot.is_running,
        "status": bot.status,
    }


@app.post("/api/auth/logout")
def auth_logout(
    session_id: str = Depends(_get_session_id),
):
    """退出登录：解绑 session，后台任务继续运行不受影响"""
    with _lock:
        _session_to_mobile.pop(session_id, None)
    _save_sessions()
    return {"success": True}


@app.get("/api/status")
def get_status(bot: ParkingBot = Depends(get_bot)):
    """获取运行状态"""
    return {
        "is_running": bot.is_running,
        "status": bot.status,
        "current_trade_no": bot.current_trade_no,
        "deadline_ts": bot.deadline_ts,
    }


@app.get("/api/logs")
def get_logs(bot: ParkingBot = Depends(get_bot)):
    """获取日志"""
    return {"logs": bot.logs}


@app.get("/api/config")
def get_config(bot: ParkingBot = Depends(get_bot)):
    """获取配置"""
    # 如果 bot 没有登录信息，返回 401 而不是返回空配置
    if not bot.config.get("mobile"):
        raise HTTPException(status_code=401, detail="请先登录")
    cfg = dict(bot.config)
    cfg["token"] = bot.token
    return cfg


@app.post("/api/config")
def update_config(config: ConfigModel, bot: ParkingBot = Depends(get_bot)):
    """更新配置并持久化"""
    if bot.is_running:
        raise HTTPException(status_code=400, detail="请先停止机器人后再修改配置")
    bot.update_config(config.model_dump())
    mobile_key = bot.config.get("mobile", "")
    if mobile_key:
        _save_config(mobile_key, bot.config)
    return {"message": "配置已保存"}


@app.get("/api/parks")
def fetch_parks(
    city_id: int, lng: str, lat: str,
    size: int = 50, page: int = 1,
    bot: ParkingBot = Depends(get_bot),
):
    """获取附近停车场列表"""
    _ensure_token(bot, lng, lat)
    _, parks = get_park_list(bot.token, city_id, lng, lat, page=page, size=min(size, 100))
    return {"parks": parks}


@app.get("/api/cities")
def fetch_cities(lng: str, lat: str, bot: ParkingBot = Depends(get_bot)):
    """获取城市列表"""
    _ensure_token(bot, lng, lat)
    _, cities = get_city_list(bot.token, lng, lat)
    return {"cities": cities}


@app.get("/api/plates")
def fetch_plates(lng: str, lat: str, bot: ParkingBot = Depends(get_bot)):
    """获取车牌列表"""
    _ensure_token(bot, lng, lat)
    _, plates = get_plate_list(bot.token, lng, lat)
    return {"plates": plates}


def _ensure_token(bot: ParkingBot, lng: str, lat: str) -> None:
    """确保 bot 有有效 token，没有则尝试重新登录"""
    if bot.token:
        return
    m = bot.config.get("mobile")
    p = bot.config.get("password_md5")
    if not m or not p:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        res = do_login(m, p, lng, lat)
        bot.token = res.get("result", {}).get("token")
        if bot.token:
            bot.config["token"] = bot.token
            _save_config(m, bot.config)
    except Exception:
        pass
    if not bot.token:
        raise HTTPException(status_code=401, detail="登录凭据已失效，请重新登录")


def _check_bot_ready(bot: ParkingBot) -> None:
    """校验配置完整（支持密码登录或验证码登录的 token）"""
    cfg = bot.config
    ok = lambda v: v is not None and v != "" and str(v).strip() != ""
    ok_id = lambda v: v is not None and (isinstance(v, (int, float)) and v > 0 or (isinstance(v, str) and v.isdigit() and int(v) > 0))
    has_auth = ok(cfg.get("mobile")) and (ok(cfg.get("password_md5")) or ok(cfg.get("token")))
    if not has_auth:
        raise HTTPException(status_code=400, detail="请先登录")
    if not ok(cfg.get("lng")) or not ok(cfg.get("lat")):
        raise HTTPException(status_code=400, detail="请填写经度、纬度")
    if not ok_id(cfg.get("city_id")):
        raise HTTPException(status_code=400, detail="请选择城市")
    if not ok_id(cfg.get("park_id")):
        raise HTTPException(status_code=400, detail="请选择停车场")
    if not ok_id(cfg.get("plate_id")):
        raise HTTPException(status_code=400, detail="请选择车牌")


@app.post("/api/action/start")
def start_bot(bot: ParkingBot = Depends(get_bot)):
    """启动机器人"""
    _check_bot_ready(bot)
    success, msg = bot.start()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/api/action/stop")
def stop_bot(bot: ParkingBot = Depends(get_bot)):
    """停止机器人"""
    success, msg = bot.stop()
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/api/action/cancel")
def cancel_current_order(bot: ParkingBot = Depends(get_bot)):
    """手动取消当前订单，主动释放车位"""
    trade_no = bot.current_trade_no
    if not trade_no:
        raise HTTPException(status_code=400, detail="当前没有进行中的订单")
    if not bot.token:
        raise HTTPException(status_code=401, detail="Token 无效，请重新登录")
    try:
        res = cancel_order(bot.token, trade_no, bot.config["lng"], bot.config["lat"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"取消请求失败：{str(e)[:80]}")
    if res.get("code") == 200:
        bot.log("[+] 手动取消订单成功，车位已释放！")
        bot.current_trade_no = None
        bot.deadline_ts = 0
        return {"message": "订单已取消，车位已释放"}
    else:
        msg = res.get("desc", "取消失败") or "取消失败"
        raise HTTPException(status_code=400, detail=str(msg))


@app.get("/api/admin/sessions")
def admin_sessions():
    """调试：查看当前活跃用户数（生产环境应加鉴权）"""
    with _lock:
        users = {}
        for mk, (bot, ts) in _bots.items():
            if mk.startswith("_tmp_"):
                continue
            users[mk[:8] + "..."] = {
                "is_running": bot.is_running,
                "status": bot.status,
                "last_active": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
            }
    return {"active_users": len(users), "users": users}


if __name__ == "__main__":
    is_dev = os.environ.get("ENV", "dev") == "dev"
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=is_dev,
        workers=1 if is_dev else int(os.environ.get("WORKERS", "1")),
    )
