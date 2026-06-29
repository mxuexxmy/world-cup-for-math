"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.models.database import init_db, get_db
from app.auth import require_admin
from app.config import SCORE_UPDATE_INTERVAL, INJURY_UPDATE_INTERVAL
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    await init_db()
    import asyncio
    asyncio.create_task(scrape_loop())
    yield


async def scrape_loop():
    """Background: FIFA score sync, daily odds, periodic injury scan."""
    import asyncio
    from datetime import datetime, timedelta
    from app.models.database import async_session_factory
    from app.services.scraper import FifaMatchSync
    from app.services.odds_scraper import OddsUpdater

    await asyncio.sleep(30)
    print("[Scheduler] FIFA score sync started")
    odds_checked_today = False
    injury_counter = 0

    while True:
        try:
            async with async_session_factory() as db:
                updates = await FifaMatchSync.fetch_live_scores(db)
                if updates:
                    print(f"[Scheduler] {len(updates)} score updates")

                now_bj = datetime.utcnow() + timedelta(hours=8)
                if now_bj.hour == 10 and not odds_checked_today:
                    count = await OddsUpdater.fetch_from_sina(db)
                    if count > 0:
                        print(f"[Scheduler] {count} odds updated")
                    odds_checked_today = True
                elif now_bj.hour != 10:
                    odds_checked_today = False

                injury_counter += SCORE_UPDATE_INTERVAL
                if injury_counter >= INJURY_UPDATE_INTERVAL:
                    injuries = await FifaMatchSync.fetch_injury_news(db)
                    if injuries:
                        print(f"[Scheduler] {len(injuries)} injury snippets found")
                    injury_counter = 0

        except Exception as e:
            print(f"[Scheduler] Error: {e}")
        await asyncio.sleep(SCORE_UPDATE_INTERVAL)


app = FastAPI(
    title="2026世界杯预测 - 体彩投注优化",
    description="2026 FIFA World Cup prediction & Chinese sports lottery betting optimizer",
    version="1.1.0",
    lifespan=lifespan,
)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

from app.routes import dashboard, matches, predictions, betting, admin

app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(matches.router, tags=["Matches"])
app.include_router(predictions.router, tags=["Predictions"])
app.include_router(betting.router, tags=["Betting"])
app.include_router(admin.router, tags=["Admin"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "tournament": "2026 FIFA World Cup", "start_date": "2026-06-11"}


@app.post("/api/refresh", dependencies=[Depends(require_admin)])
async def refresh_data(db: AsyncSession = Depends(get_db)):
    """Manually trigger FIFA score sync."""
    from app.services.scraper import FifaMatchSync
    updates = await FifaMatchSync.fetch_live_scores(db)
    return {"status": "ok", "updates": len(updates) if updates else 0}


@app.post("/api/odds/update", dependencies=[Depends(require_admin)])
async def update_odds(request: Request, db: AsyncSession = Depends(get_db)):
    """Update odds from structured JSON."""
    from app.services.odds_scraper import OddsUpdater
    data = await request.json()
    count = await OddsUpdater.update_odds_from_json(db, data)
    return {"status": "ok", "updated": count}


@app.get("/api/bankroll")
async def get_bankroll(db: AsyncSession = Depends(get_db)):
    from app.services.bet_optimizer import BetOptimizer
    optimizer = BetOptimizer(db)
    return await optimizer.get_bankroll_summary()


@app.post("/api/place-bet/{rec_id}")
async def place_bet(rec_id: int, db: AsyncSession = Depends(get_db)):
    """Place a bet from a BetRecommendation."""
    from app.services.bet_optimizer import BetOptimizer
    optimizer = BetOptimizer(db)
    result = await optimizer.place_bet(rec_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/cancel-bet/{bet_id}")
async def cancel_bet(bet_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel a pending BetLedger entry."""
    from sqlalchemy import select
    from app.models.prediction import BetLedger
    result = await db.execute(select(BetLedger).where(BetLedger.id == bet_id))
    bet = result.scalar_one_or_none()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.result != "pending":
        raise HTTPException(status_code=400, detail="Cannot cancel settled bet")
    await db.delete(bet)
    await db.commit()
    return {"status": "ok", "cancelled": bet_id}
