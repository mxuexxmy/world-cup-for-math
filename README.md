<p align="center">

  <h1 align="center">🏆 世界杯赌神</h1>

  <p align="center">2026 FIFA World Cup Prediction & Betting Optimizer</p>

</p>



---



基于 **Elo + 泊松分布 + GradientBoosting** 的 2026 美加墨世界杯预测与体彩投注优化原型。对比竞彩赔率发现价值投注，用凯利准则推荐单关与过关组合。



## ✨ 功能



- 🔮 **AI 比分预测** — Elo 40% + 泊松 35% + ML 25%（权重可在 `.env` 调整）

- 💰 **价值投注** — 对比竞彩/模型赔率，筛选正 EV 机会

- 🎯 **凯利 + 止损** — 1/4 凯利；连续 3 负后降至 1/8 凯利

- 🔗 **过关优化** — 2/3/4 串 1 组合（独立假设，文档已注明相关性风险）

- 📊 **FIFA 同步** — `fifa_match_id` 匹配比分；管理后台与 API 共用结算流水线

- 📒 **虚拟记账** — 串关单条账本、按全场结算



## 🚀 快速开始

### Windows（推荐，无需懂命令行）

1. 安装 [Python 3.10+](https://www.python.org/downloads/)，安装时勾选 **Add python.exe to PATH**
2. 详细步骤见项目根目录 **`使用说明.txt`**（纯文本，双击用记事本打开）
3. 双击 **`首次安装.bat`**（仅需一次，含虚拟环境与模型训练）
4. 以后双击 **`启动.bat`** 即可使用
5. 可选：**`重置数据.bat`** / **`更新模型.bat`**

> `.bat` 为 **GBK 编码**（适配中文 Windows 的 cmd）。若从 Git 克隆后双击脚本时中文乱码，在项目根目录执行 `python scripts/generate_windows_bats.py` 重新生成即可。

### 命令行

```bash
pip install -r requirements.txt
cp .env.example .env
python -m alembic upgrade head
python data/historical/build_dataset.py   # 首次或更新历史赛果
python data/train_model.py
python data/seed/seed_database.py
python run.py
```

### Docker



```bash

docker build -t worldcup-math .

docker run -p 8000:8000 worldcup-math

```



## 🏗 技术栈



| 层 | 技术 |

|---|---|

| 后端 | Python · FastAPI · SQLAlchemy (aiosqlite) |

| 机器学习 | scikit-learn GradientBoosting · scipy 泊松 |

| 前端 | Jinja2 · Chart.js · HTMX |

| 数据 | FIFA API · 种子 JSON · 竞彩示例/模型生成 |



## 📁 项目结构



```

├── app/

│   ├── main.py                 # FastAPI + 后台调度

│   ├── config.py               # 环境变量配置

│   ├── auth.py                 # 可选 ADMIN_TOKEN 鉴权

│   ├── models/                 # ORM（球队/比赛/赔率/预测/投注等）

│   ├── routes/                 # 页面与 API 路由

│   └── services/

│       ├── predictor.py        # 集成预测

│       ├── scraper.py          # FifaMatchSync（FIFA 比分同步）

│       ├── bet_optimizer.py    # 凯利 + 过关

│       └── match_settlement.py # 赛后 Elo/投注/预测统一流水线

├── data/

│   ├── seed/                   # teams.json / groups.json / group_schedule.json / knockout_schedule.json

│   └── train_model.py          # 训练 GradientBoosting → model.pkl

├── tests/                      # pytest

└── .github/workflows/ci.yml

```



## 📊 预测模型



```

最终 = Elo × ELO_WEIGHT + 泊松 × POISSON_WEIGHT + ML × ML_WEIGHT

默认 0.40 / 0.35 / 0.25

```



训练：`python data/train_model.py`（StatsBomb 开源 2018+2022 世界杯 128 场赛果；`data/historical/world_cup_matches.json`）

数据库迁移：`python -m alembic upgrade head`（替代删库 `create_all`）



## 📡 数据来源



| 数据 | 来源 | 说明 |

|------|------|------|

| 小组赛 + 淘汰赛 `fifa_match_id` | FIFA API | 种子时拉取；离线兜底 `group_schedule.json` / `knockout_schedule.json` |

| 实时比分 / 球场 / 裁判 | FIFA API | 每 120s；`POST /api/refresh`（需 ADMIN_TOKEN 若已配置） |

| 竞彩赔率 | `odds_real.json` / `odds_real.example.json` / 模型生成 | `POST /api/odds/update` 注入 |

| 球队实力快照 | `data/seed/teams.json` | 初始化写入 |



## 🔗 API



```

GET  /                         仪表盘

GET  /match/{id}               比赛详情

GET  /betting/                 投注推荐

POST /api/predict-all          生成全部未赛预测

POST /api/refresh              刷新 FIFA 比分（写操作需鉴权）

POST /api/place-bet/{rec_id}   跟注（BetRecommendation.id）

POST /api/cancel-bet/{bet_id}  撤销（BetLedger.id）

```



管理后台 `/admin`：录入比分/赔率、一键全量预测。设置 `ADMIN_TOKEN` 后请求头加 `X-Admin-Token`。



## ⚙️ 配置



见 `.env.example`。常用项：`FIFA_SEASON_ID`、`INITIAL_BANKROLL`、`STOP_LOSS_STREAK`、`ADMIN_TOKEN`。



## 🧪 测试



```bash

pytest tests/ -q

```



## ⚠️ 声明



仅供学习研究。投注有风险，请理性购彩。



## Star History



<a href="https://www.star-history.com/?repos=world+cup+for+math%2Fworld+cup+for+math&type=date&legend=top-left">

 <picture>

   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=world cup for math/world cup for math&type=date&theme=dark&legend=top-left" />

   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=world cup for math/world cup for math&type=date&legend=top-left" />

   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=world cup for math/world cup for math&type=date&legend=top-left" />

 </picture>

</a>

