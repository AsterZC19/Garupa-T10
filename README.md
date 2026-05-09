# バンドリ！ ガールズバンドパーティ！T10 Web Event Tracker

WebSite: [Garupa T10](https://t10.starminus.uk/)

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

## TODO
- [x] 查询玩家主乐队信息
- [ ] 并行优化
- [x] 记录玩家色段及 T10 信息并展示

## 致谢
感谢 Gemini-2.5-Pro, Gemini-3-Pro 以及 GPT-5.5 完成了 95% 的代码设计。