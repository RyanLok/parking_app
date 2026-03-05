# 部署指南

## 架构

```
用户浏览器  →  Vercel (前端静态站)  →  云服务器 (后端 API)
                                        ↕
                                    data/ (配置持久化)
```

---

## 一、后端部署（云服务器）

### 1. 环境准备

```bash
# 安装 Python 3.10+
sudo apt update && sudo apt install -y python3 python3-pip python3-venv

# 上传代码到服务器
scp -r backend/ user@your-server:/opt/parking_app/backend/

# 创建虚拟环境
cd /opt/parking_app/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `start.sh`，修改 `CORS_ORIGINS` 为你的 Vercel 域名：

```bash
export CORS_ORIGINS="https://your-app.vercel.app"
```

如有自定义域名，逗号分隔追加即可。

### 3. 启动方式

**方式 A：systemd（推荐）**

```bash
# 编辑 parking.service 中的路径和域名
sudo cp parking.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable parking
sudo systemctl start parking

# 查看日志
sudo journalctl -u parking -f
```

**方式 B：手动运行**

```bash
cd /opt/parking_app/backend
source venv/bin/activate
ENV=prod CORS_ORIGINS="https://your-app.vercel.app" ./start.sh
```

### 4. Nginx 反向代理（推荐）

```nginx
server {
    listen 443 ssl;
    server_name api.your-domain.com;

    ssl_certificate     /etc/ssl/your-cert.pem;
    ssl_certificate_key /etc/ssl/your-key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> **重要**：后端必须通过 HTTPS 暴露，否则 Vercel（HTTPS）的前端无法请求 HTTP 的后端（混合内容被浏览器拦截）。

### 5. 防火墙

```bash
# 只允许 Nginx 转发，不直接暴露 8000 端口
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp
```

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
