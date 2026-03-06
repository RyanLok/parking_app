import datetime
import time
import threading
from api_simulator import do_login, get_space_list, book_space, get_order, cancel_order, get_user_info

class ParkingBot:
    def __init__(self):
        self.is_running = False
        self.thread = None
        self.status = "未启动"
        self.logs = []
        self.config = {
            "mobile": "",
            "password_md5": "",
            "lng": "",
            "lat": "",
            "park_id": 0,
            "city_id": 0,
            "plate_id": 0,
            "expect_leave_time": "19:00",
            "start_time": "08:00:00",
            "end_time": "10:30:00",
            "poll_interval": 5,
            "safe_cancel_advance": 10
        }
        self.token = None
        self._on_token_change = None  # 回调：token 变更时通知外部持久化
        self._on_log = None  # 回调：日志变更时通知外部持久化
        self._log_save_counter = 0  # 节流计数器，每 5 条日志存一次盘
        
        # State info for frontend
        self.current_trade_no = None
        self.deadline_ts = 0
        self.last_poll_log_time = 0

    def log(self, msg):
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {msg}"
        self.logs.append(log_entry)
        print(log_entry)
        if len(self.logs) > 200:
            self.logs = self.logs[-200:]
        # 节流持久化：每 5 条日志或重要日志时存盘
        self._log_save_counter += 1
        is_important = any(k in msg for k in ('✅', '❌', '启动', '停止', '退出', '成功', '失败', '过期'))
        if self._on_log and (self._log_save_counter >= 5 or is_important):
            self._log_save_counter = 0
            try:
                self._on_log(self)
            except Exception:
                pass

    def start(self):
        if self.is_running:
            return False, "Bot is already running"
        
        self.is_running = True
        self.status = "正在运行"
        self.log("🤖 全自动霸占车位机器人后台任务已启动...")
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True, "Bot started successfully"

    def stop(self):
        if not self.is_running:
            return False, "Bot is not running"
        
        self.is_running = False
        self.status = "已停止"
        self.log("🛑 收到停止指令，机器人将在当前操作完成后退出后台循环...")
        return True, "Bot stop requested"

    def update_config(self, new_config):
        # 确保数值类型字段不会被存为字符串
        for k in ('park_id', 'city_id', 'plate_id', 'poll_interval', 'safe_cancel_advance'):
            if k in new_config and new_config[k] is not None:
                try:
                    new_config[k] = int(new_config[k])
                except (ValueError, TypeError):
                    pass
        self.config.update(new_config)
        self.log("⚙️ 配置已更新")

    @staticmethod
    def _parse_time(t_str):
        """解析时间字符串，支持 HH:MM:SS 和 HH:MM 两种格式"""
        try:
            return datetime.datetime.strptime(t_str, "%H:%M:%S").time()
        except ValueError:
            return datetime.datetime.strptime(t_str, "%H:%M").time()

    # The original loop, adapted to check self.is_running
    def _run_loop(self):
        while self.is_running:
            # ====== 1. 最高优先级：检查是否已有进行中的订单（含外部下单）======
            # 无论是否在工作时段，都需要检测和管理已有订单
            try:
                existing = self._check_existing_order()
            except Exception as e:
                self.log(f"[-] 检查在途订单异常: {str(e)[:80]}")
                existing = None

            if existing:
                trade_no = existing["tradeNo"]
                enter_deadline_ms = existing.get("enterDeadline")
                space_info = existing.get("spaceInfo", {})
                space_code = space_info.get("spaceCode", "未知")
                park_name = existing.get("parkName", "")

                self.log(f"🔄 检测到已有进行中的订单 {trade_no}")
                self.log(f"   车位: {park_name} {space_code}")
                self.status = "已抢到车位"
                self.current_trade_no = trade_no

                if enter_deadline_ms:
                    deadline_dt = datetime.datetime.fromtimestamp(enter_deadline_ms / 1000.0)
                    self.deadline_ts = enter_deadline_ms / 1000.0
                    now_ts = time.time()

                    sleep_seconds = int(self.deadline_ts - now_ts) + 5
                    if sleep_seconds < 0:
                        sleep_seconds = 5

                    self.log(f"   最晚入场期限: {deadline_dt.strftime('%H:%M:%S')}")

                    safe_keep_seconds = sleep_seconds - self.config["safe_cancel_advance"]
                    if safe_keep_seconds < 0:
                        safe_keep_seconds = 1

                    self.log(f"   将在 {safe_keep_seconds // 60} 分 {safe_keep_seconds % 60} 秒后主动取消续租...")

                    for remaining in range(safe_keep_seconds, 0, -1):
                        if not self.is_running or not self.current_trade_no:
                            break
                        if remaining % 60 == 0:
                            self.log(f"距离主动释放续租开抢，还剩大约 {remaining // 60} 分钟...")
                        time.sleep(1)

                    if not self.current_trade_no:
                        self.log("ℹ️ 订单已被手动取消，立即继续抢位...")
                    elif self.is_running:
                        self.log(f"⏰ 时间到！准备主动取消订单 {trade_no}...")
                        try:
                            cancel_res = cancel_order(self.token, trade_no, self.config["lng"], self.config["lat"])
                        except Exception as e:
                            self.log(f"[-] 取消订单异常: {e}")
                            cancel_res = {}
                        if cancel_res.get("code") == 200:
                            self.log("[+] 主动取消成功！立刻发起新的占坑循环！")
                        else:
                            self.log(f"[-] 主动取消失败: {cancel_res.get('desc')}")

                else:
                    self.log("[-] 无法获取入场期限，默认休眠 14.5 分钟...")
                    self.deadline_ts = time.time() + (14.5 * 60)
                    for _ in range(int(14.5 * 60)):
                        if not self.is_running or not self.current_trade_no:
                            break
                        time.sleep(1)

                self.current_trade_no = None
                self.deadline_ts = 0
                continue  # 订单管理完毕，回到循环顶部重新检测

            # ====== 2. 时间控制：不在工作时段则休眠 ======
            now = datetime.datetime.now()
            current_time = now.time()

            start_work_time = self._parse_time(self.config["start_time"])
            end_work_time = self._parse_time(self.config["end_time"])
            # 处理跨天工作时间配置
            is_working_time = False
            if start_work_time <= end_work_time:
                is_working_time = start_work_time <= current_time <= end_work_time
            else:
                is_working_time = current_time >= start_work_time or current_time <= end_work_time
                
            if not is_working_time:
                self.status = "待机休眠中"
                tomorrow_start = datetime.datetime.combine(
                    now.date() + datetime.timedelta(days=1 if current_time > end_work_time else 0), 
                    start_work_time
                )
                wait_seconds = (tomorrow_start - now).total_seconds()
                
                self.log(f"😴 当前时间不在开工时段 ({self.config['start_time']}-{self.config['end_time']})。")
                self.log(f"进入待机模式，预计将在 {wait_seconds / 3600:.1f} 小时后自动苏醒...")
                
                # 休眠期间每 30 秒醒来检查一次是否有外部订单
                slept = 0
                woke_for_order = False
                while slept < wait_seconds and self.is_running:
                    # 每 30 秒检查一次外部订单
                    nap = min(30, wait_seconds - slept)
                    for _ in range(int(nap)):
                        if not self.is_running:
                            break
                        time.sleep(1)
                    slept += nap
                    if not self.is_running:
                        break
                    # 检查是否有外部新订单
                    try:
                        ext = self._check_existing_order()
                    except Exception:
                        ext = None
                    if ext:
                        self.log("🔔 待机期间检测到新订单！立即唤醒处理...")
                        woke_for_order = True
                        break  # 跳出休眠，回到主循环顶部处理订单
                
                if self.is_running and not woke_for_order:
                    self.log("⏰ 早上好！开工执行任务...")
                    self.status = "正在运行"
                continue

            # ====== 3. 工作逻辑：搜索并预定车位 ======
            self.status = "正在寻找车位"
            try:
                status_code, trade_no = self._attempt_book_cycle()
            except Exception as e:
                self.log(f"[-] 搜索或预定发生异常: {str(e)[:100]}...")
                self.log("⚠️ 网络不稳定，机器人不会停止工作，将延时5秒后自动重试补单...")
                status_code, trade_no = "CONTINUE_POLL", None
                time.sleep(5)
            
            if status_code == "NEED_LOGIN":
                pwd = self.config.get("password_md5") or ""
                if not pwd.strip():
                    self.log("[-] 验证码登录用户 Token 已过期，无法自动续登，请重新登录。")
                    self.is_running = False
                    self.status = "Token过期请重登"
                    break
                self.log("正在尝试重新登录获取最新 Token...")
                try:
                    login_res = do_login(self.config["mobile"], pwd, self.config["lng"], self.config["lat"])
                    self.token = login_res.get("result", {}).get("token")
                except Exception as e:
                    self.log(f"[-] 重新登录网络异常: {e}")
                    self.token = None
                if self.token:
                    self.config["token"] = self.token
                    self.log("重新登录成功！可以继续发包...")
                    # 回调持久化
                    if self._on_token_change:
                        try:
                            self._on_token_change(self)
                        except Exception:
                            pass
                else:
                    self.log("[-] 重新登录失败，无法拿到有效 Token，延迟 10 秒后重试。")
                    time.sleep(10)
                    continue
                    
            elif status_code == "SUCCESS_BOOKED" and trade_no:
                self.status = "已抢到车位"
                self.current_trade_no = trade_no
                self.log(f"🚗 成功锁定车位！正在查询订单信息...")
                
                try:
                    order_res = get_order(self.token, trade_no, self.config["lng"], self.config["lat"])
                except Exception as e:
                    self.log(f"[-] 查询订单详情异常: {e}")
                    order_res = {}
                
                enter_deadline_ms = order_res.get("result", {}).get("enterDeadline")
                
                if enter_deadline_ms:
                    deadline_dt = datetime.datetime.fromtimestamp(enter_deadline_ms / 1000.0)
                    self.deadline_ts = enter_deadline_ms / 1000.0
                    now_ts = time.time()
                    
                    sleep_seconds = int(self.deadline_ts - now_ts) + 5
                    if sleep_seconds < 0:
                        sleep_seconds = 5
                        
                    self.log(f"订单最晚入场期限为: {deadline_dt.strftime('%H:%M:%S')}")
                    
                    safe_keep_seconds = sleep_seconds - self.config["safe_cancel_advance"]
                    if safe_keep_seconds < 0:
                        safe_keep_seconds = 1
                        
                    self.log(f"策略：将在 {safe_keep_seconds // 60} 分 {safe_keep_seconds % 60} 秒后主动取消，无缝续租...")
                    
                    for remaining in range(safe_keep_seconds, 0, -1):
                        if not self.is_running or not self.current_trade_no:
                            break
                        if remaining % 60 == 0:
                            self.log(f"距离主动释放续租开抢，还剩大约 {remaining // 60} 分钟...")
                        time.sleep(1)
                    
                    # 如果是手动取消导致跳出，不需要再取消
                    if not self.current_trade_no:
                        self.log("ℹ️ 订单已被手动取消，立即继续抢位...")
                    elif self.is_running:
                        self.log(f"⏰ 时间到！准备主动取消上笔订单 {trade_no} 以防止系统发呆...")
                        try:
                            cancel_res = cancel_order(self.token, trade_no, self.config["lng"], self.config["lat"])
                        except Exception as e:
                            self.log(f"[-] 发起取消订单请求异常: {e}")
                            cancel_res = {}
                            
                        if cancel_res.get("code") == 200:
                            self.log("[+] 主动取消成功！已回归票池，立刻发起新的占坑循环抢回！")
                        else:
                            self.log(f"[-] 主动取消失败: {cancel_res.get('desc')}")
                            
                else:
                    self.log("[-] 获取订单过期时间失败，退回默认预估休眠 14.5 分钟...")
                    self.deadline_ts = time.time() + (14.5 * 60)
                    for _ in range(int(14.5 * 60)):
                        if not self.is_running or not self.current_trade_no: break
                        time.sleep(1)
                        
                self.current_trade_no = None
                self.deadline_ts = 0
                
            elif status_code == "CONTINUE_POLL":
                # Check is_running during brief sleep
                for _ in range(self.config["poll_interval"]):
                    if not self.is_running: break
                    time.sleep(1)
        
        # Cleanup when exited
        self.status = "未启动"
        self.current_trade_no = None
        self.deadline_ts = 0
        self.log("⏹️ 后台机器人循环彻底退出。")


    def _check_existing_order(self):
        """调用 /app/v3/user/info 检查是否已有进行中的订单"""
        if not self.token:
            return None
        try:
            res = get_user_info(self.token, self.config["lng"], self.config["lat"])
        except Exception:
            return None
        if res.get("code") == 4014:
            return None  # token 过期，交给后续登录逻辑处理
        share_order = (res.get("result") or {}).get("shareOrder")
        if share_order and share_order.get("tradeNo"):
            return share_order
        return None

    def _attempt_book_cycle(self):
        if not self.token:
            return "NEED_LOGIN", None
            
        space_res, valid_spaces = get_space_list(
            self.token, 
            self.config["park_id"], 
            self.config["city_id"], 
            self.config["lng"], 
            self.config["lat"], 
            leave_time_str=self.config["expect_leave_time"]
        )
        
        if space_res.get("code") == 4014:
            return "NEED_LOGIN", None
        
        if not valid_spaces:
            # only log occasionally to avoid spam
            current_t = time.time()
            if current_t - self.last_poll_log_time >= self.config.get("poll_interval", 10):
                 self.log("当前没有符合条件的车位，持续轮询中...")
                 self.last_poll_log_time = current_t
            return "CONTINUE_POLL", None
        
        target_space = valid_spaces[0]
        target_space_id = target_space.get("id")
        space_name = target_space.get("spaceName")
        self.log(f"⭐ 发现空位: {space_name} (ID: {target_space_id})! 发起预定...")
        
        book_res = book_space(self.token, self.config["park_id"], target_space_id, self.config["plate_id"], self.config["lng"], self.config["lat"])
        
        if book_res.get("code") == 4014:
            return "NEED_LOGIN", None
        elif book_res.get("code") == 200:
            self.log("✅ 成功抢到车位并下达订单！")
            trade_no = book_res.get("result", {}).get("tradeNo")
            return "SUCCESS_BOOKED", trade_no
        else:
            self.log(f"被截胡或下单失败: {book_res.get('desc')}")
            return "CONTINUE_POLL", None
