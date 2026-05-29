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

## 项目结构

```
├── start.sh                   # 一键启动脚本
├── build.sh                   # 前端构建脚本
├── backend/
│   ├── run.py                 # Uvicorn 启动入口
│   ├── requirements.txt       # Python 依赖
│   ├── data/                  # SQLite 数据库目录
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
