<p align="center">
  <h1 align="center">🏆 世界杯赌神</h1>
  <p align="center">2026 FIFA World Cup Prediction & Betting Optimizer</p>
</p>

---

基于 **Elo 评分 + 泊松分布 + GradientBoosting** 的 2026 美加墨世界杯 AI 预测系统。对比中国体育彩票竞彩赔率，自动发现价值投注，用凯利准则推荐最优投注组合。

## ✨ 功能

- 🔮 **AI 比分预测** — 三层集成模型（Elo 40% + 泊松 35% + ML 25%），输出胜平负概率、预期进球、比分分布
- 💰 **价值投注发现** — 对比竞彩官方赔率，自动识别正期望值投注机会
- 🎯 **凯利准则** — 1/4 凯利保守策略，控制单注 ≤ 5% 总资金，单日 ≤ 20%
- 🔗 **过关优化** — 枚举 2串1 组合，最大化期望收益
- 📊 **实时比分** — FIFA 官方 API 自动抓取，比赛结束自动结算 Elo 和投注盈亏
- 📒 **虚拟记账** — 跟注、撤销、自动结算，实时追踪盈亏

## 🚀 快速开始

```bash
pip install -r requirements.txt
python data/seed/seed_database.py   # 初始化 48 队 + 104 场比赛
python run.py                       # 启动 http://localhost:8000
```

## 🏗 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python · FastAPI · SQLAlchemy (aiosqlite) |
| 机器学习 | scikit-learn GradientBoosting · scipy 泊松分布 |
| 前端 | Jinja2 · Chart.js · HTMX |
| 数据 | FIFA API · sporttery.cn · Transfermarkt |

## 📁 项目结构

```
├── app/
│   ├── main.py                 # FastAPI 入口 + 后台调度
│   ├── config.py               # 全局配置
│   ├── models/                 # ORM 模型 (6 张表)
│   ├── routes/                 # 路由 (仪表盘/比赛/预测/投注/管理)
│   ├── services/               # 核心逻辑
│   │   ├── predictor.py        # 预测引擎 (三层集成)
│   │   ├── elo.py              # Elo 评分系统
│   │   ├── bet_optimizer.py    # 投注优化 (凯利+过关)
│   │   ├── scraper.py          # FIFA API 比分爬虫
│   │   ├── odds_scraper.py     # 竞彩赔率更新
│   │   └── feature_engine.py   # 33 维特征工程
│   └── templates/              # Jinja2 HTML 模板
├── data/seed/                  # 种子数据 (48队/12组/104场)
├── run.py
└── requirements.txt
```

## 📊 预测模型

```
最终预测 = Elo × 40% + 泊松 xG × 35% + GradientBoosting × 25%
```

- **Elo 评分** — 基于 FIFA 官方排名，含主场加成 (L1/L2/L3)
- **泊松分布** — Dixon-Coles 低分修正 (rho=-0.13)，8×8 比分矩阵
- **GradientBoosting** — 33 维特征 (基础实力/球员因子/主场/场外因素)

## 📡 数据来源

| 数据 | 来源 |
|------|------|
| 实时比分 | FIFA 官方 API |
| 竞彩赔率 | 中国体育彩票竞彩网 |
| 球队排名 | FIFA 官方排名 (2026.6) |
| 球员身价 | Transfermarkt |
| 平均年龄 | 官方 26 人名单 |
| 球场数据 | FIFA 官方场馆信息 |

## 🔗 API

```
GET  /                       仪表盘
GET  /match/{id}             比赛详情
GET  /betting/               投注推荐
POST /api/refresh            刷新比分
POST /api/predict-all        生成预测
POST /betting/api/optimize   运行优化器
POST /api/place-bet/{id}     跟注
POST /api/place-bet/{id}?cancel=1  撤销
```

## ⚙️ 配置

`app/config.py`:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ELO_K_FACTOR` | 60 | Elo 灵敏度 |
| `KELLY_FRACTION` | 0.25 | 凯利保守系数 |
| `MAX_STAKE_PCT` | 0.05 | 单注上限 |
| `SCORE_UPDATE_INTERVAL` | 120s | 比分刷新间隔 |

## ⚠️ 声明

本项目仅供学习和研究使用。投注有风险，请理性购彩，远离非法赌博。
