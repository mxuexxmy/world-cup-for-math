"""Betting optimizer — Kelly criterion + parlay optimization for 竞彩足球."""
import json
import itertools
from typing import List, Dict, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.config import (
    INITIAL_BANKROLL,
    MAX_STAKE_PCT,
    MAX_DAILY_STAKE_PCT,
    MIN_ODDS,
    MAX_PARLAY,
    KELLY_FRACTION,
    STOP_LOSS_STREAK,
    STOP_LOSS_FRACTION,
)
from app.models.match import Match
from app.models.odds import Odds
from app.models.prediction import Prediction, BetRecommendation, BetLedger
from app.services.odds_parser import OddsParser


def _match_winner(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "主胜"
    if away_score > home_score:
        return "客胜"
    return "平局"


class BetOptimizer:
    """Find value bets and optimal parlay combinations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _effective_kelly_fraction(self) -> float:
        """Apply stop-loss: reduce Kelly after consecutive losses."""
        result = await self.db.execute(
            select(BetLedger)
            .where(BetLedger.result.in_(["won", "lost"]))
            .order_by(BetLedger.settled_at.desc())
            .limit(STOP_LOSS_STREAK)
        )
        recent = result.scalars().all()
        if len(recent) >= STOP_LOSS_STREAK and all(b.result == "lost" for b in recent):
            return STOP_LOSS_FRACTION
        return KELLY_FRACTION

    async def optimize(self) -> Dict:
        """Run full optimization: find value bets and parlay combos."""
        result = await self.db.execute(
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.prediction),
                selectinload(Match.odds),
            )
            .where(Match.status == "scheduled")
            .order_by(Match.match_date)
        )
        matches = result.scalars().all()

        for m in matches:
            if not m.odds:
                await OddsParser.update_odds_for_match(self.db, m.id)

        result = await self.db.execute(
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.prediction),
                selectinload(Match.odds),
            )
            .where(Match.status == "scheduled")
            .order_by(Match.match_date)
        )
        matches = [m for m in result.scalars().all() if m.prediction and m.odds]

        summary = await self.get_bankroll_summary()
        bankroll = summary["bankroll"]
        kelly_mult = await self._effective_kelly_fraction()

        value_bets = []
        for m in matches:
            for selection, result_key in [("主胜", "home"), ("平局", "draw"), ("客胜", "away")]:
                ev, pred_prob, imp_prob, odds_val = self._evaluate_bet(m, result_key)
                if ev > 0 and odds_val >= MIN_ODDS:
                    kelly = self._kelly_fraction(pred_prob, odds_val, kelly_mult)
                    value_bets.append({
                        "match": m,
                        "selection": selection,
                        "result_key": result_key,
                        "odds": odds_val,
                        "predicted_prob": pred_prob,
                        "implied_prob": imp_prob,
                        "ev": ev,
                        "kelly": kelly,
                    })

        value_bets.sort(key=lambda x: x["ev"], reverse=True)

        await self._clear_old_recommendations()
        singles = value_bets[:10]
        for bet in singles:
            stake = self._calculate_stake(bet["kelly"], bankroll)
            rec = BetRecommendation(
                created_at=datetime.utcnow(),
                strategy_name=f"{bet['match'].home_team.name_cn} vs {bet['match'].away_team.name_cn} — {bet['selection']}",
                matches_json=json.dumps([{
                    "match_id": bet["match"].id,
                    "home_team": bet["match"].home_team.name_cn,
                    "away_team": bet["match"].away_team.name_cn,
                    "selection": bet["selection"],
                    "odds": bet["odds"],
                    "predicted_prob": round(bet["predicted_prob"], 4),
                }], ensure_ascii=False),
                bet_type="单关",
                total_odds=round(bet["odds"], 2),
                expected_value=round(bet["ev"], 4),
                kelly_fraction=round(bet["kelly"], 4),
                suggested_stake=round(stake, 2),
                explanation=self._explain_bet(bet),
            )
            self.db.add(rec)

        parlays = self._generate_parlays(value_bets[:20], bankroll, kelly_mult)
        for p in parlays:
            rec = BetRecommendation(
                created_at=datetime.utcnow(),
                strategy_name=p["name"],
                matches_json=json.dumps(p["matches"], ensure_ascii=False),
                bet_type=p["type"],
                total_odds=round(p["total_odds"], 2),
                expected_value=round(p["ev"], 4),
                kelly_fraction=round(p["kelly"], 4),
                suggested_stake=round(p["stake"], 2),
                explanation=p["explanation"],
            )
            self.db.add(rec)

        await self.db.commit()

        return {
            "value_bets_count": len(singles),
            "parlay_count": len(parlays),
            "total_bets": len(singles) + len(parlays),
            "bankroll": bankroll,
            "kelly_fraction": kelly_mult,
        }

    def _evaluate_bet(self, match, result_key: str) -> Tuple[float, float, float, float]:
        if not match.prediction or not match.odds:
            return 0, 0, 0, 1.0

        probs = {
            "home": match.prediction.prob_home_win,
            "draw": match.prediction.prob_draw,
            "away": match.prediction.prob_away_win,
        }
        odds_vals = {
            "home": match.odds.win_odds,
            "draw": match.odds.draw_odds,
            "away": match.odds.lose_odds,
        }

        pred_prob = probs.get(result_key, 0)
        odds_val = odds_vals.get(result_key, 1.0)

        if not odds_val or odds_val <= 1.0:
            return 0, pred_prob, 0, 1.0

        imp = OddsParser.implied_probability(
            odds_vals["home"], odds_vals["draw"], odds_vals["away"]
        )
        imp_prob = imp.get(result_key, 0)
        ev = pred_prob * (odds_val - 1) - (1 - pred_prob)
        return ev, pred_prob, imp_prob, odds_val

    @staticmethod
    def _kelly_fraction(prob: float, odds: float, fraction: float = KELLY_FRACTION) -> float:
        if odds <= 1.0:
            return 0
        b = odds - 1
        kelly = (prob * b - (1 - prob)) / b
        return max(0, kelly * fraction)

    @staticmethod
    def _calculate_stake(kelly: float, bankroll: float) -> float:
        stake = bankroll * kelly
        return min(stake, bankroll * MAX_STAKE_PCT)

    def _generate_parlays(
        self, value_bets: List[dict], bankroll: float, kelly_mult: float
    ) -> List[dict]:
        results = []
        seen_keys = set()

        for size in range(2, min(MAX_PARLAY, 4) + 1):
            for combo in itertools.combinations(value_bets, size):
                match_ids = {b["match"].id for b in combo}
                if len(match_ids) < size:
                    continue

                key = tuple(sorted((b["match"].id, b["selection"]) for b in combo))
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                total_odds = 1.0
                combined_prob = 1.0
                for b in combo:
                    total_odds *= b["odds"]
                    combined_prob *= b["predicted_prob"]

                if total_odds < MIN_ODDS:
                    continue

                ev = combined_prob * (total_odds - 1) - (1 - combined_prob)
                kelly = self._kelly_fraction(combined_prob, total_odds, kelly_mult)
                stake = self._calculate_stake(kelly, bankroll)

                if ev <= 0.02:
                    continue

                bet_type = f"{size}串1"
                legs = [
                    {
                        "match_id": b["match"].id,
                        "home_team": b["match"].home_team.name_cn,
                        "away_team": b["match"].away_team.name_cn,
                        "selection": b["selection"],
                        "odds": b["odds"],
                        "predicted_prob": round(b["predicted_prob"], 4),
                    }
                    for b in combo
                ]
                results.append({
                    "name": f"{bet_type}: " + "+".join(b["selection"] for b in combo),
                    "type": bet_type,
                    "matches": legs,
                    "total_odds": total_odds,
                    "ev": ev,
                    "kelly": kelly,
                    "stake": stake,
                    "explanation": (
                        f"组合概率 {combined_prob:.4%}，组合赔率 {total_odds:.2f}。"
                        f"独立假设下期望值 +{ev*100:.2f}%（同轮次比赛存在相关性，实际风险更高）"
                    ),
                })

        results.sort(key=lambda x: x["ev"], reverse=True)
        return results[:8]

    def _explain_bet(self, bet: dict) -> str:
        edge = (bet["predicted_prob"] - bet["implied_prob"]) * 100
        return (
            f"模型预测概率 {bet['predicted_prob']:.1%} > 市场隐含概率 {bet['implied_prob']:.1%}，"
            f"优势 {edge:.1f}%。期望值 +{bet['ev']*100:.2f}%"
        )

    async def _clear_old_recommendations(self):
        from sqlalchemy import delete
        await self.db.execute(delete(BetRecommendation))
        await self.db.flush()

    async def get_recommendations(self) -> dict:
        result = await self.db.execute(
            select(BetRecommendation)
            .order_by(BetRecommendation.expected_value.desc())
            .limit(15)
        )
        recs = result.scalars().all()
        summary = await self.get_bankroll_summary()
        return {
            "recommendations": [r.to_dict() for r in recs],
            "bankroll": summary["bankroll"],
            "daily_bet": summary["today_staked"],
            "profit": summary["total_profit"],
        }

    async def place_bet(self, recommendation_id: int) -> dict:
        result = await self.db.execute(
            select(BetRecommendation).where(BetRecommendation.id == recommendation_id)
        )
        rec = result.scalar_one_or_none()
        if not rec:
            return {"error": "Recommendation not found"}

        legs_data = rec.get_matches()
        if not legs_data:
            return {"error": "No matches in recommendation"}

        summary = await self.get_bankroll_summary()
        if rec.suggested_stake > summary["today_remaining"]:
            return {"error": "Exceeds daily stake limit"}

        if rec.bet_type == "单关" or len(legs_data) == 1:
            leg = legs_data[0]
            entry = BetLedger(
                recommendation_id=rec.id,
                match_id=leg.get("match_id", 0),
                bet_type=rec.bet_type,
                selection=leg.get("selection", ""),
                stake=rec.suggested_stake,
                odds=leg.get("odds", rec.total_odds),
                result="pending",
            )
            self.db.add(entry)
            await self.db.commit()
            summary = await self.get_bankroll_summary()
            return {
                "status": "ok",
                "placed": 1,
                "total_stake": rec.suggested_stake,
                "bankroll": summary["bankroll"],
                "today_staked": summary["today_staked"],
                "today_remaining": summary["today_remaining"],
            }

        legs = [
            {
                "match_id": leg["match_id"],
                "selection": leg["selection"],
                "odds": leg["odds"],
                "result": "pending",
            }
            for leg in legs_data
        ]
        entry = BetLedger(
            recommendation_id=rec.id,
            match_id=legs[0]["match_id"],
            bet_type=rec.bet_type,
            selection=rec.bet_type,
            stake=rec.suggested_stake,
            odds=rec.total_odds,
            result="pending",
        )
        entry.set_legs(legs)
        self.db.add(entry)
        await self.db.commit()
        summary = await self.get_bankroll_summary()
        return {
            "status": "ok",
            "placed": 1,
            "total_stake": rec.suggested_stake,
            "bankroll": summary["bankroll"],
            "today_staked": summary["today_staked"],
            "today_remaining": summary["today_remaining"],
        }

    async def get_bankroll_summary(self) -> dict:
        result = await self.db.execute(
            select(BetLedger).where(BetLedger.result.in_(["won", "lost"]))
        )
        settled = result.scalars().all()
        total_profit = sum(b.profit for b in settled)

        now_bj = datetime.utcnow() + timedelta(hours=8)
        today_start = now_bj.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start - timedelta(hours=8)

        result = await self.db.execute(
            select(BetLedger).where(BetLedger.created_at >= today_start_utc)
        )
        today_bets = result.scalars().all()
        today_staked = sum(b.stake for b in today_bets)

        result = await self.db.execute(
            select(BetLedger).where(BetLedger.result == "pending")
        )
        pending = result.scalars().all()

        bankroll = INITIAL_BANKROLL + total_profit
        daily_limit = bankroll * MAX_DAILY_STAKE_PCT

        return {
            "bankroll": round(bankroll, 2),
            "initial": INITIAL_BANKROLL,
            "total_profit": round(total_profit, 2),
            "today_staked": round(today_staked, 2),
            "today_remaining": round(max(0, daily_limit - today_staked), 2),
            "daily_limit": round(daily_limit, 2),
            "pending_count": len(pending),
            "pending_stake": round(sum(b.stake for b in pending), 2),
            "settled_count": len(settled),
        }

    @staticmethod
    async def settle_bets_for_match(
        db: AsyncSession, match_id: int, home_score: int, away_score: int
    ):
        winner = _match_winner(home_score, away_score)

        result = await db.execute(
            select(BetLedger).where(BetLedger.result == "pending")
        )
        pending = result.scalars().all()
        settled_count = 0

        for bet in pending:
            legs = bet.get_legs()
            if legs:
                if not any(leg["match_id"] == match_id for leg in legs):
                    continue
                for leg in legs:
                    if leg["match_id"] == match_id:
                        leg["result"] = "won" if leg["selection"] == winner else "lost"
                bet.set_legs(legs)

                if any(leg["result"] == "lost" for leg in legs):
                    bet.result = "lost"
                    bet.profit = -bet.stake
                    bet.settled_at = datetime.utcnow()
                    settled_count += 1
                elif all(leg["result"] == "won" for leg in legs):
                    bet.result = "won"
                    bet.profit = bet.stake * (bet.odds - 1)
                    bet.settled_at = datetime.utcnow()
                    settled_count += 1
                else:
                    await db.flush()
                    continue
            elif bet.match_id == match_id:
                if bet.selection == winner:
                    bet.result = "won"
                    bet.profit = bet.stake * (bet.odds - 1)
                else:
                    bet.result = "lost"
                    bet.profit = -bet.stake
                bet.settled_at = datetime.utcnow()
                settled_count += 1

        if settled_count:
            await db.commit()

        return settled_count
