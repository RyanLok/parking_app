import hmac
import hashlib
import time
import datetime
import requests
import json
import urllib.parse

# 密钥
APP_KEY = b'95703ea9e01a3f31bd9432e1728cb905'

# 基础公共参数
BASE_PARAMS = {
    "appId": "ap7i2Zk74mWmjwKnQT",
    "appVersion": "4.5.2",
    "clientType": "1",
    "deviceId": "9e85a2c6c82464a8aa9ef6c2d9b30d884",
    "deviceIP": "10.0.2.15",
    "deviceModel": "ALN-AL00",
    "mobileSystem": "android12",
    "networkType": "1",
    "screen": "1440x2560",
    "version": "1.0.0",
}

def generate_sign(params):
    """
    根据给定的参数字典生成 sign 签名
    """
    # 过滤掉 sign 和空值
    filtered_params = {k: v for k, v in params.items() if k != 'sign' and v is not None}
    
    # 按字典序排序
    sorted_keys = sorted(filtered_params.keys())
    
    # 拼接字符串 key=value&key=value
    parts = []
    for k in sorted_keys:
        parts.append(f"{k}={filtered_params[k]}")
    data_str = "&".join(parts)
    
    # HMAC-MD5 加密并转大写
    data_bytes = data_str.encode('utf-8')
    sign = hmac.new(APP_KEY, data_bytes, hashlib.md5).hexdigest().upper()
    return sign

def generate_timestamp():
    """
    生成毫秒级时间戳
    """
    return str(int(time.time() * 1000))

def send_sms_code(mobile, user_lng, user_lat):
    """
    发送验证码到手机
    URL: https://pm.airparking.cn/app/sms/login
    仅传 mobile（明文），不传 smsCode，接口会下发短信
    """
    url = "https://pm.airparking.cn/app/sms/login"

    headers = {
        "version-tag": "release",
        "username": "",
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    params = BASE_PARAMS.copy()
    params.update({
        "mobile": str(mobile).strip(),
        "userLng": str(user_lng),
        "userLat": str(user_lat),
        "timestamp": generate_timestamp(),
    })
    params["sign"] = generate_sign(params)

    response = requests.post(url, headers=headers, data=params)
    return response.json()


def login_with_sms(mobile_b64, sms_code, user_lng, user_lat):
    """
    验证码登录：传入 base64 编码的 mobile + 6 位验证码
    接口：/app/user/login2（与密码登录同一端点，传 smsCode 替代 password）
    """
    url = "https://pm.airparking.cn/app/user/login2"

    headers = {
        "version-tag": "release",
        "username": "",
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    params = BASE_PARAMS.copy()
    params.update({
        "mobile": mobile_b64,
        "smsCode": str(sms_code).strip(),
        "userLng": str(user_lng),
        "userLat": str(user_lat),
        "timestamp": generate_timestamp(),
    })
    params["sign"] = generate_sign(params)

    response = requests.post(url, headers=headers, data=params)
    return response.json()


def do_login(mobile, password, user_lng, user_lat):
    """
    模拟登录请求
    """
    url = "https://pm.airparking.cn/app/user/login2"
    
    headers = {
        "version-tag": "release",
        "username": "",
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # 组装参数
    params = BASE_PARAMS.copy()
    params.update({
        "mobile": mobile,
        "password": password,
        "userLng": str(user_lng),
        "userLat": str(user_lat),
        "timestamp": generate_timestamp()
    })
    
    # 生成签名并加入参数
    params["sign"] = generate_sign(params)
    
    print(f"[*] 执行登录请求, mobile: {mobile}")
    response = requests.post(url, headers=headers, data=params)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}\n")
    return response.json()

def get_space_list(token, park_id, city_id, user_lng, user_lat, leave_time_str=None):
    """
    获取停车场车位情况
    :param leave_time_str: 期望的最早离开时间，格式如 '19:00'，只看 rentEndTime 晚于该时间的车位
    """
    url = "https://pm.airparking.cn/app/v3/space/list/version2"
    
    headers = {
        "version-tag": "release",
        # 接口请求头中 username 取 token 值
        "username": token, 
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # 组装参数
    params = BASE_PARAMS.copy()
    
    # 注意 filter 的传法，签名时传原始 JSON 字符串，而不是 URL Encode 之后的值
    # requests 库的 data 如果传字典，会自动 URL Encode，这是正确的行为
    params.update({
        "cityId": str(city_id),
        "count": "10",
        "filter": '{"hours":0}', 
        "page": "1",
        "parkId": str(park_id),
        "size": "10",
        "sort": "1",
        "spaceIds": "", # 原请求是空的
        "timestamp": generate_timestamp(),
        "token": token,
        "userLat": str(user_lat),
        "userLng": str(user_lng)
    })
    
    # 生成签名
    params["sign"] = generate_sign(params)
    
    print(f"[*] 获取车位列表, parkId: {park_id}")
    response = requests.post(url, headers=headers, data=params)
    # print(f"Status Code: {response.status_code}")
    res_json = response.json()
    if res_json.get("code") == 200:
        spaces = res_json.get("result", {}).get("list", [])
        
        # 定义目标离场时间戳 (今天指定时间)
        target_leave_timestamp = 0
        if leave_time_str:
            today = datetime.datetime.now().date()
            time_obj = datetime.datetime.strptime(leave_time_str, "%H:%M").time()
            target_dt = datetime.datetime.combine(today, time_obj)
            target_leave_timestamp = int(target_dt.timestamp() * 1000)
            # print(f"[*] 正在过滤可停到 {leave_time_str} ({target_dt}) 之后的车位...")

        valid_spaces = []
        for space in spaces:
            rent_end_time = space.get("rentEndTime", 0)
            if leave_time_str and rent_end_time <= target_leave_timestamp:
                continue # 如果要求了时间且可用时间不足，则跳过
            valid_spaces.append(space)
            
        print(f"成功获取并筛选到 {len(valid_spaces)} 个符合条件的车位 (总计 {len(spaces)} 个):\n" + "-"*40)
        
        # 注释掉长打印，避免刷屏
        # for space in valid_spaces:
        #     space_id = space.get("id")
        #     space_name = space.get("spaceName")
        #     ...
        
        # 为了方便调用者拿到可用车位并立刻预定，我们直接返回列表
        return res_json, valid_spaces
            
    elif res_json.get("code") == 4014:
        print("[-] Token 登录过期！")
    else:
        print(f"响应异常: {response.text}")
        
    return res_json, []

def book_space(token, park_id, space_id, plate_id, user_lng, user_lat):
    """
    锁定下单车位
    :param plate_id: 你的车辆 ID (如抓包里的 1393416)
    :param space_id: 要预定的车位 ID
    """
    url = "https://pm.airparking.cn/app/v3/order/bookSpace"
    
    headers = {
        "version-tag": "release",
        "username": token,
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = BASE_PARAMS.copy()
    params.update({
        "parkId": str(park_id),
        "plateId": str(plate_id),
        "spaceId": str(space_id),
        "timestamp": generate_timestamp(),
        "token": token,
        "userLat": str(user_lat),
        "userLng": str(user_lng)
    })

    params["sign"] = generate_sign(params)
    
    print(f"[*] 准备下单锁定车位, spaceId: {space_id}, plateId: {plate_id}")
    response = requests.post(url, headers=headers, data=params)
    res_json = response.json()
    
    if res_json.get("code") == 200:
        order = res_json.get("result", {})
        print("[+] ✨ 下单成功！\n" + "="*40)
        print(f"订单号(tradeNo): {order.get('tradeNo')}")
        print(f"预定车牌(plateNo): {order.get('plateNo')}")
        
        space_info = order.get('spaceInfo', {})
        print(f"预定车位: {space_info.get('parkName')} {space_info.get('spaceCode')}")
        
        start_t = datetime.datetime.fromtimestamp(order.get('availableStartTime', 0) / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
        end_t = datetime.datetime.fromtimestamp(order.get('availableEndTime', 0) / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
        print(f"可用时间段: {start_t} 到 {end_t}")
        print(f"入场提示: {order.get('spaceMessage')}")
        print("="*40)
    elif res_json.get("code") == 4014:
        print("[-] Token 登录过期！")
    else:
        print(f"[-] 下单失败，返回信息: {response.text}")
        
    return res_json

def get_order(token, trade_no, user_lng, user_lat):
    """
    获取订单详情
    """
    url = "https://pm.airparking.cn/app/v3/order/get"
    
    headers = {
        "version-tag": "release",
        "username": token,
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = BASE_PARAMS.copy()
    params.update({
        "tradeNo": str(trade_no),
        "timestamp": generate_timestamp(),
        "token": token,
        "userLat": str(user_lat),
        "userLng": str(user_lng)
    })

    params["sign"] = generate_sign(params)
    
    response = requests.post(url, headers=headers, data=params)
    res_json = response.json()
    
    if res_json.get("code") == 4014:
        print("[-] 获取订单时 Token 登录过期！")
    
    return res_json

def cancel_order(token, trade_no, user_lng, user_lat):
    """
    手动主动取消订单
    """
    url = "https://pm.airparking.cn/app/v3/order/newCancel"
    
    headers = {
        "version-tag": "release",
        "username": token,
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = BASE_PARAMS.copy()
    params.update({
        "additional": "",
        "cause": "6",
        "timestamp": generate_timestamp(),
        "token": token,
        "tradeNo": str(trade_no),
        "userLat": str(user_lat),
        "userLng": str(user_lng)
    })

    params["sign"] = generate_sign(params)
    
    response = requests.post(url, headers=headers, data=params)
    res_json = response.json()
    
    if res_json.get("code") == 4014:
        print("[-] 取消订单时 Token 登录过期！")
        
    return res_json

def get_park_list(token, city_id, user_lng, user_lat, page=1, size=50):
    """
    获取附近停车场列表及其车位状态
    对齐 filterList 接口：orderBy=0，size 增大以拉取更多结果
    """
    url = "https://pm.airparking.cn/app/park/filterList"

    headers = {
        "version-tag": "release",
        "username": token,
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = BASE_PARAMS.copy()
    params.update({
        "cityId": str(city_id),
        "count": str(size),
        "isNear": "0",
        "orderBy": "0",
        "page": str(page),
        "serviceStatus": "1",
        "size": str(size),
        "timestamp": generate_timestamp(),
        "token": token,
        "userLat": str(user_lat),
        "userLng": str(user_lng)
    })

    params["sign"] = generate_sign(params)
    
    # print(f"[*] 获取停车场列表 (City: {city_id}, Page: {page})")
    response = requests.post(url, headers=headers, data=params)
    res_json = response.json()
    
    if res_json.get("code") == 200:
        parks = res_json.get("result", {}).get("list", [])
        # print(f"成功获取到 {len(parks)} 个停车场数据")
        return res_json, parks
    elif res_json.get("code") == 4014:
        print("[-] 获取停车场列表 Token 登录过期！")
    else:
        print(f"[-] 获取停车场列表失败: {response.text}")
        
    return res_json, []

def get_city_list(token, user_lng, user_lat):
    """
    获取支持的城市列表
    """
    url = "https://pm.airparking.cn/app/index/cities"
    
    headers = {
        "version-tag": "release",
        "username": token,
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = BASE_PARAMS.copy()
    params.update({
        "clientType": "1",
        "timestamp": generate_timestamp(),
        "token": token,
        "userLat": str(user_lat),
        "userLng": str(user_lng)
    })

    params["sign"] = generate_sign(params)
    
    response = requests.post(url, headers=headers, data=params)
    res_json = response.json()
    
    cities = []
    if res_json.get("code") == 200:
        cities = res_json.get("result", [])
        
    return res_json, cities

def get_plate_list(token, user_lng, user_lat):
    """
    获取用户绑定的车牌列表
    """
    url = "https://pm.airparking.cn/app/v3/user/plate"
    
    headers = {
        "version-tag": "release",
        "username": token,
        "Host": "pm.airparking.cn",
        "User-Agent": "okhttp/3.11.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    params = BASE_PARAMS.copy()
    params.update({
        "clientType": "1",
        "timestamp": generate_timestamp(),
        "token": token,
        "userLat": str(user_lat),
        "userLng": str(user_lng)
    })

    params["sign"] = generate_sign(params)
    
    response = requests.post(url, headers=headers, data=params)
    res_json = response.json()
    
    plates = []
    if res_json.get("code") == 200:
        plates = res_json.get("result", [])
        
    return res_json, plates

