# 部署指南

## 架构

```
用户浏览器  →  Vercel (前端静态站)  →  云服务器 (后端 API)
                                        ↕
                                    data/ (配置持久化)
```

---

## 一、后端部署（云服务器）

### 方式 A：宝塔部署（推荐）

#### 1. 安装 Python 项目管理器

宝塔面板 → **软件商店** → 搜索 **Python 项目管理器** → 安装

#### 2. 上传代码

- 用宝塔 **文件** 或 SFTP 把 `backend/` 目录上传到服务器，例如：`/www/wwwroot/parking/backend/`
- 确保 `main.py`、`bot.py`、`api_simulator.py`、`requirements.txt` 都在该目录下

#### 3. 添加 Python 项目

宝塔 → **软件商店** → **Python 项目管理器** → **添加项目**

| 配置项 | 值 |
|--------|-----|
| 项目名称 | parking-api |
| 项目路径 | `/www/wwwroot/parking/backend` |
| Python 版本 | 3.10 或以上 |
| 框架 | 其他 |
| 启动方式 | **gunicorn** |
| 启动文件 | `main:app` |
| 运行端口 | 8000 |

若使用 gunicorn，**启动参数必须包含**：`-k uvicorn.workers.UvicornWorker -w 1`

> ⚠️ **workers 必须为 1**：bot 实例在进程内存中，多 worker 无法共享。否则 `/api/status` 会交替返回不同实例，出现「未启动」与「正在寻找车位」闪烁。`/api/status` 的 `_debug` 含 `pid=xxx`，若不同请求的 pid 不同则说明是多进程。

若无 gunicorn 选项，可选 **uvicorn**，启动文件填 `main:app`。

**环境变量**（点击「环境变量」或「项目设置」添加）：

| 变量名 | 值 |
|--------|-----|
| ENV | prod |
| CORS_ORIGINS | https://你的项目.vercel.app |
| PORT | 8000 |

#### 4. 创建站点并配置反向代理

宝塔 → **网站** → **添加站点**

- 域名：`api.你的域名.com`（或单独二级域名）
- 根目录：任意（不填也可）
- PHP 版本：纯静态

**站点创建后** → 点击站点 → **设置** → **反向代理** → **添加反向代理**

| 配置项 | 值 |
|--------|-----|
| 代理名称 | parking-api |
| 目标 URL | `http://127.0.0.1:8000` |
| 发送域名 | `$host` |

保存后，在 **配置文件** 里确认 `location /` 被正确代理到 8000。

#### 5. 配置 SSL

站点设置 → **SSL** → **Let's Encrypt** → 申请证书 → 强制 HTTPS

> 必须开启 HTTPS，否则 Vercel 前端无法访问（Mixed Content 拦截）

#### 6. 确保项目运行

Python 项目管理器 → 找到 parking-api → 点击 **启动** 或 **重启**，状态变为「运行中」

---

### 方式 B：命令行 + systemd（无宝塔）

`start.sh` 使用 **Gunicorn + UvicornWorker** 启动，进程管理更稳健。

#### 1. 环境准备

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
scp -r backend/ user@your-server:/opt/parking_app/backend/

cd /opt/parking_app/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. 配置环境变量

编辑 `start.sh`，修改 `CORS_ORIGINS` 为你的 Vercel 域名。

#### 3. 启动方式

```bash
./start.sh   # 或用 systemd：
sudo cp parking.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable parking
sudo systemctl start parking
```

#### 4. Nginx 反向代理

按需配置 Nginx 反代到 8000 端口，并绑定 SSL 证书。

---

## 二、前端部署（Vercel）

### 1. 修改 API 地址

编辑 `frontend/.env.production`：

```
VITE_API_BASE=https://api.your-domain.com/api
```

### 2. 推送到 Git 仓库

```bash
cd parking_app
git init
git add .
git commit -m "init: parking app"
git remote add origin git@github.com:your-user/parking-app.git
git push -u origin main
```

### 3. Vercel 导入项目

1. 打开 [vercel.com](https://vercel.com)，点击 **Add New → Project**
2. 导入你的 GitHub 仓库
3. 配置：
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. 在 **Environment Variables** 中添加：
   - `VITE_API_BASE` = `https://api.your-domain.com/api`
5. 点击 **Deploy**

### 4. 自定义域名（可选）

在 Vercel 项目 Settings → Domains 中绑定你的域名。
绑定后记得更新后端的 `CORS_ORIGINS` 环境变量。

---

## 三、部署检查清单

- [ ] 后端 HTTPS 可访问：`curl https://api.your-domain.com/api/admin/sessions`
- [ ] 前端可访问：打开 Vercel 域名，确认登录页正常
- [ ] 登录测试：输入账号密码，确认能成功登录
- [ ] 跨域正常：浏览器控制台无 CORS 报错
- [ ] 配置持久化：保存配置后，后端重启，再次登录确认配置恢复
- [ ] `data/` 目录权限：`chmod 700 /opt/parking_app/backend/data`

---

## 四、常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 前端提示"无法连接服务器" | 后端未启动或 CORS 未配置 | 检查后端状态 + `CORS_ORIGINS` |
| 浏览器报 Mixed Content | 后端用 HTTP，前端在 HTTPS | 后端必须上 HTTPS（Nginx SSL） |
| 登录后刷新回到登录页 | 后端重启，session 映射丢失 | 正常现象，重新登录即可 |
| 保存配置 422 错误 | 前端 Config 类型字段不全 | 检查前后端 ConfigModel 字段一致 |
| **状态/日志交替闪烁** | **workers > 1，请求落到不同进程** | **gunicorn 必须 `-w 1`**；请求 `/api/status` 查看 `_debug.pid` 是否变化 |
