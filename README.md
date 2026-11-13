# 📈 股票预警系统

A 股 + 港股 + ETF 实时行情监控与 MACD 预警系统，前端 Vue 3 + Vite，后端 Python FastAPI。

## 功能概览

### 行情与自选
- 支持 A 股（主板/创业板/科创板/北交所）、港股、ETF
- 自选股管理：添加/删除/批量导入导出，支持代码、中文名、拼音首字母模糊搜索
- 卡片视图 + 列表视图切换，列表支持涨跌幅/现价/成交量等多列排序
- 卡片拖拽排序，列表涨跌幅排序

### K 线与图表
- 分时图 / 日 K / 周 K / 月 K，使用 lightweight-charts 渲染
- 均线系统：MA5 / MA10 / MA20 / MA60 / MA250 可独立开关
- 成交量副图 + MACDFS 副图，上下视图时间轴同步
- K 线详情页支持图表标注（便签）功能

### 预警系统
- MACD 金叉 / 死叉预警，卡片边框闪烁提示
- 涨停 / 跌停预警（自动识别板块涨跌幅限制）
- 价格预警：设置突破价 / 跌破价，触发时弹窗提醒
- 预警侧边栏集中展示所有预警信号
- 预警跑马灯在导航栏滚动播报
- 提示音 / 语音播报（Web Speech API），可切换开关
- 单股预警静音（🔔 按钮切换）

### 其他
- 做 T 计算器：输入金额和成本，自动计算可买股数与盈利
- 红涨绿跌 / 绿涨红跌主题切换
- 交易时段自动加速刷新（5s），非交易时段 30s
- SQLite 本地数据缓存，减少 API 请求
- 一键打包为单端口生产模式

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Vue 3 + Vite + Pinia + vue-router + lightweight-charts |
| 后端 | Python FastAPI + Uvicorn |
| 数据库 | SQLite（watchlist / cache / annotations） |
| 数据源 | 新浪财经（行情 + 搜索）+ 腾讯财经（K 线 + 分时） |

## 快速开始

### 开发模式（前后端分离，支持热更新）

```bash
# 终端 1：启动后端
cd backend
pip install -r requirements.txt
python run.py          # → http://localhost:8000

# 终端 2：启动前端
cd frontend
npm install
npm run dev            # → http://localhost:3001（自动代理 /api → :8000）
```

### 生产模式（一键启动，单端口）

```bash
./start.sh             # 自动构建前端 → 启动后端 → 打开浏览器
# 访问 http://localhost:8000
```

### 仅构建前端

```bash
./build.sh             # 输出到 backend/static/
```

## Docker Compose 部署

单容器设计：Node 阶段仅用于编译前端，最终镜像只有 Python 运行时；FastAPI 同时托管 `/api/*` 接口与前端静态页，前端使用相对路径（`baseURL: '/api'`），因此无需额外 Nginx 或跨域配置。

```bash
cp .env.example .env
docker compose up -d --build
# 访问 http://localhost:8001
```

- **端口**：`.env` 的 `STOCK_ALERT_PORT` 只改宿主机映射端口（默认 8001），容器内固定 8000。
- **数据持久化**：SQLite 位于容器内 `/app/data/stock.db`（自选股 + 行情缓存 + 标注），由命名卷 `stock-alert_stock-alert-data` 保存。`docker compose down`、重建镜像、升级版本都不会丢数据；只有 `docker compose down -v` 会清空。
- **时区**：镜像内安装 `tzdata` 并设置 `TZ=Asia/Shanghai`。后端用 `date.today()` 生成分时数据时间戳，容器跑在 UTC 会导致分时图错位。
- **代理**：容器默认直连行情接口，不会继承终端的 `HTTP_PROXY`。若必须走宿主机代理（如 Clash），在 `.env` 中设置：
  ```dotenv
  STOCK_HTTP_PROXY=http://host.docker.internal:7897
  STOCK_HTTPS_PROXY=http://host.docker.internal:7897
  ```
  然后 `docker compose up -d` 重启容器使环境变量生效。
- **构建源**：默认从 Docker Hub / npm / PyPI 官方源拉取。若 NAS 或国内网络拉不动，在 `.env` 中设置 `NODE_IMAGE`、`PYTHON_IMAGE`、`NPM_REGISTRY`、`PIP_INDEX_URL`（`.env.example` 内有一组已验证可用的国内源），再 `docker compose up -d --build`。
- **数据备份**：`docker compose exec app sh -c 'cp /app/data/stock.db /app/data/backup.db'`，或从宿主机 `docker cp stock-alert:/app/data/stock.db ./`。
- **健康检查**：镜像内置 `/health` 探活（30s 间隔），`docker compose ps` 中显示 `healthy` 即服务可用。

### 从 Git 拉取并一键更新

部署机上把仓库 clone 下来，用 `deploy.sh` 完成「拉代码 → 重建 → 重启」：

```bash
git clone https://github.com/guoymwork/stock-alert.git
cd stock-alert
cp .env.example .env
./deploy.sh
```

> `STOCK_BUILD_CONTEXT` 可以直接填 Git URL 让 compose 每次构建自动 clone，但该 clone 由 Docker daemon 执行，若 daemon 访问不了 GitHub 会失败。这种情况保持默认的本地副本 + `deploy.sh` 即可。

排错：

| 现象 | 处理 |
|------|------|
| 页面能开但行情/K线全空 | `docker compose logs -f app` 找异常；`global flags not at the start` 说明命中了旧版正则写法（见下方兼容性说明） |
| 交易时段不刷新 | 确认 `TZ=Asia/Shanghai`，`docker compose exec app date` 应为东八区 |
| 端口被占用 | 修改 `.env` 的 `STOCK_ALERT_PORT` 后 `docker compose up -d` |
| 卡在 `load metadata` / 基础镜像 401 | 镜像加速源不可用，按上文配置 `NODE_IMAGE`、`PYTHON_IMAGE` 后重新构建 |
| 构建时 npm 失败 | 确认 `frontend/package-lock.json` 已提交，镜像内使用 `npm ci` |
| 构建时 pip 超时 | 在 `.env` 配置 `PIP_INDEX_URL`（如阿里云 PyPI 镜像）后重新构建 |
| 构建卡在 `resolve image config for docker.io/docker/dockerfile:1` | 不要在 Dockerfile 首行加 `# syntax=docker/dockerfile:1`，它会让 BuildKit 额外拉取前端镜像；本项目只用标准语法 |

### Python 3.11+ 兼容性

`backend/app/services/data_fetcher.py` 中的代码前缀剥离曾写作 `re.sub(r"^(?i)(hk|sh|sz)", ...)`。Python 3.11 要求内联全局标志必须位于表达式最前面，否则编译期直接抛 `re.error: global flags not at the start`，会导致**实时行情、分时、K 线全部失败**。现改为 `flags=re.IGNORECASE` 参数形式。

## 项目结构

```
├── start.sh                   # 一键启动脚本
├── build.sh                   # 前端构建脚本
├── Dockerfile                 # 多阶段构建（Node 编译前端 → Python 运行后端）
├── docker-compose.yml         # 服务 + 命名卷 + 端口/环境变量
├── docker-entrypoint.sh       # 确保 SQLite 数据目录存在
├── deploy.sh                  # 部署机：git pull + compose 重建
├── .env.example               # 可配置项示例
├── .dockerignore
├── backend/
│   ├── run.py                 # Uvicorn 启动入口
│   ├── requirements.txt       # Python 依赖
│   ├── data/                  # SQLite 数据库目录（运行时生成，不入库）
│   ├── static/                # 前端构建产物（npm run build 输出）
│   └── app/
│       ├── main.py            # FastAPI 应用 + 静态文件托管
│       ├── config.py          # 配置（缓存 TTL 等）
│       ├── models/schemas.py  # Pydantic 数据模型
│       ├── routers/           # API 路由
│       │   ├── stocks.py      # 行情/K线/MACD/搜索
│       │   ├── watchlist.py   # 自选股 CRUD
│       │   └── annotations.py # 便签 CRUD
│       └── services/          # 业务逻辑
│           ├── data_fetcher.py # 新浪 + 腾讯数据抓取 + 缓存
│           ├── database.py    # SQLite 初始化 + 操作
│           ├── indicators.py  # MACD 计算 + 金叉死叉检测
│           ├── stock_list.py  # 股票搜索（代码/中文/拼音）
│           └── cache.py       # 缓存封装
└── frontend/
    ├── vite.config.js         # Vite 配置（代理 + 构建输出）
    ├── package.json
    └── src/
        ├── main.js            # Vue 入口
        ├── App.vue            # 根组件
        ├── api/stock.js       # Axios API 封装
        ├── assets/main.css    # 全局样式 + CSS 变量
        ├── components/        # 通用组件
        │   ├── StockCard.vue       # 自选股卡片
        │   ├── KlineChart.vue      # K 线图（lightweight-charts）
        │   ├── MacdChart.vue       # MACD 副图
        │   ├── MiniSparkline.vue   # 迷你走势 Canvas
        │   ├── AddStockModal.vue   # 添加自选弹窗
        │   └── AppHeader.vue       # 导航栏 + 跑马灯
        ├── views/
        │   ├── HomeView.vue        # 首页（卡片/列表/预警/设置）
        │   └── DetailView.vue      # 详情页（K线/MACD/标注/计算器）
        ├── stores/
        │   ├── stock.js            # Pinia 行情状态
        │   └── settings.js         # Pinia 设置（主题/刷新/提示音）
        ├── router/index.js         # Vue Router
        └── utils/indicators.js     # 前端 MACD 计算 + 交叉检测
```

## 环境要求

- Python 3.9+
- Node.js 16+
- 网络连接（需访问新浪/腾讯财经 API）

## License

MIT
