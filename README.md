# バンドリ！ ガールズバンドパーティ！T10 Web Event Tracker

## ✨ 功能列表

- **活动选择**：自由选择查看当前或任一过往活动的数据。
- **实时档位榜**：展示 Top 10 玩家的排名、当前PT、时速、签名等信息。
- **时速曲线图**：查看PT变化曲线。

## 🛠️ 技术栈

- **前端**: Vue 3, Vite, Tailwind CSS, Chart.js
- **后端**: Python 3, Flask, SQLAlchemy
- **数据源**: [Bestdori](https://bestdori.com/)

## 🚀 本地开发指南

### 1. 环境准备

- 安装 [Python 3.8+](https://www.python.org/downloads/)
- 安装 [Node.js 16+](https://nodejs.org/)
- 克隆本项目到本地: `git clone <repository-url>`

### 2. 后端设置

```bash
# 进入后端目录
cd backend

# (推荐) 创建并激活虚拟环境
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 前端设置

```bash
# 进入前端目录
cd frontend

# 安装 Node.js 依赖
npm install
```

### 4. 运行项目

你需要**同时运行**后端和前端两个服务。

- **启动后端服务** (在项目根目录 `App/` 下运行):
  ```bash
  python backend/app.py
  ```
  后端会运行在 `http://localhost:5000`。

- **启动前端开发服务** (在 `App/frontend/` 目录下运行):
  ```bash
  npm run dev
  ```
  前端会运行在 `http://localhost:5173`，并自动代理 API 请求到后端。

现在，你可以通过浏览器访问 `http://localhost:5173` 来查看应用了。

## 部署到服务器

### 1. 打包前端

在部署前，你需要先将前端应用打包成静态文件。

```bash
# 进入前端目录
cd frontend

# 执行打包命令
npm run build
```

打包后的文件会生成在 `frontend/dist` 目录下。Flask 后端被配置为可以自动托管这些静态文件。

### 2. 运行后端 (生产环境)

在生产环境中，不应使用 Flask 内置的开发服务器。推荐使用 Gunicorn 或 uWSGI 等 WSGI 服务器。

**使用 Gunicorn 示例:**

```bash
# 安装 Gunicorn
pip install gunicorn

# 从项目根目录 App/ 启动 Gunicorn
# -w 4 表示启动 4 个工作进程
# -b 0.0.0.0:5000 表示监听在 5000 端口
# backend.app:app 指向 backend/app.py 文件中的 app 实例
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app
```

### 3. (可选) 使用 Nginx 作为反向代理

为了获得更好的性能和安全性，通常会使用 Nginx 在 Gunicorn 前面作为反向代理。

**Nginx 简易配置示例 (`/etc/nginx/sites-available/your_project`):**

```nginx
server {
    listen 80;
    server_name your_domain.com; # 你的域名或服务器IP

    location / {
        # 将所有请求转发给 Gunicorn
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```


## 最后
感谢 Gemini-2.5-Pro 完成了 100% 的代码设计。