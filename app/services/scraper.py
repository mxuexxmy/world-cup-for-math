"""FIFA match sync — live scores, results, injuries (Dongqiudi fallback)."""
import json
import httpx
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import FIFA_COMPETITION_ID, FIFA_SEASON_ID
from app.models.match import Match
from app.models.team import Team
from app.models.prediction import Prediction, MatchResult


class FifaMatchSync:
    """Sync live match data from FIFA API; Dongqiudi as optional fallback."""

    BASE_URL = "https://dongqiudi.com"
    API_BASE = "https://www.dongqiudi.com"
    FIFA_API = "https://api.fifa.com/api/v3/calendar/matches"

    # FIFA API MatchStatus codes
    FIFA_STATUS_MAP = {
        0: "finished",
        1: "scheduled",
        3: "live",
        4: "cancelled",
    }

    FIFA_HTTP_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    @staticmethod
    async def fetch_live_scores(db: AsyncSession) -> List[Dict]:
        """
        Fetch live match scores from multiple sources.
        Tries FIFA API first (most reliable), then Dongqiudi fallback.

        Returns list of updates applied (for logging).
        """
        updates = []

        # Method 1: FIFA API (primary, reliable)
        updates = await FifaMatchSync._fetch_fifa_scores(db)

        # Method 2: Dongqiudi API (fallback, often blocked)
        if not updates:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        "https://dongqiudi.com/api/v3/competition/1/matches",
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept": "application/json",
                        },
                        follow_redirects=True,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict) and "data" in data:
                            raw = FifaMatchSync._extract_scores(data["data"])
                            for u in raw:
                                await FifaMatchSync._apply_score_update(db, u)
                            updates = raw
            except Exception as e:
                print(f"[Scraper] Dongqiudi fetch: {e}")

        return updates

    @staticmethod
    def _fifa_locale_desc(items, locale: str = "en-GB") -> str:
        """Extract localized description from FIFA API [{Locale, Description}, ...]."""
        if not items:
            return ""
        if isinstance(items, str):
            return items
        for item in items:
            if item.get("Locale") == locale:
                return item.get("Description", "") or ""
        return items[0].get("Description", "") or ""

    @staticmethod
    def _parse_fifa_datetime(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.strptime(
                date_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z"
            )
        except ValueError:
            return None

    @staticmethod
    async def _find_match_by_fifa_id(
        db: AsyncSession, fifa_match_id: str
    ) -> Optional[Match]:
        if not fifa_match_id:
            return None
        result = await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(Match.fifa_match_id == str(fifa_match_id))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _resolve_team_id(db: AsyncSession, fifa_code: Optional[str]) -> Optional[int]:
        code = fifa_code or "TBD"
        result = await db.execute(select(Team).where(Team.fifa_code == code))
        team = result.scalar_one_or_none()
        if team:
            return team.id
        result = await db.execute(select(Team).where(Team.fifa_code == "TBD"))
        tbd = result.scalar_one_or_none()
        return tbd.id if tbd else None

    @staticmethod
    async def _sync_fifa_teams(
        db: AsyncSession,
        match: Match,
        home_code: str,
        away_code: str,
    ) -> bool:
        """Update knockout placeholders when FIFA assigns real teams."""
        new_home_id = await FifaMatchSync._resolve_team_id(db, home_code or "TBD")
        new_away_id = await FifaMatchSync._resolve_team_id(db, away_code or "TBD")
        changed = False
        if new_home_id and match.home_team_id != new_home_id:
            match.home_team_id = new_home_id
            changed = True
        if new_away_id and match.away_team_id != new_away_id:
            match.away_team_id = new_away_id
            changed = True
        if changed:
            await db.refresh(match, ["home_team", "away_team"])
        return changed

    @staticmethod
    async def _find_match_by_fifa_codes(
        db: AsyncSession,
        home_code: str,
        away_code: str,
        fifa_dt: Optional[datetime],
    ) -> Optional[Match]:
        """Match DB row by FIFA country codes and kickoff time proximity."""
        result = await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(
                Match.home_team.has(fifa_code=home_code),
                Match.away_team.has(fifa_code=away_code),
            )
        )
        candidates = result.scalars().all()
        if not candidates:
            return None
        if not fifa_dt:
            return candidates[0]

        best_match = None
        best_diff = timedelta(days=999)
        fifa_naive = fifa_dt.replace(tzinfo=None)
        for candidate in candidates:
            diff = abs(candidate.match_date - fifa_naive)
            if diff < best_diff:
                best_diff = diff
                best_match = candidate

        if best_diff > timedelta(days=2):
            return None
        return best_match

    @staticmethod
    def _sync_fifa_match_metadata(match: Match, fifa_row: Dict) -> bool:
        """Sync stadium, weather and referee from a FIFA calendar row. Returns True if changed."""
        changed = False
        stadium = fifa_row.get("Stadium") or {}
        stadium_name = FifaMatchSync._fifa_locale_desc(stadium.get("Name"))
        city_name = FifaMatchSync._fifa_locale_desc(stadium.get("CityName"))

        if stadium_name and match.stadium != stadium_name:
            match.stadium = stadium_name
            match.venue = stadium_name
            changed = True
        if city_name and match.city != city_name:
            match.city = city_name
            changed = True

        weather = fifa_row.get("Weather") or {}
        temp = weather.get("Temperature")
        humidity = weather.get("Humidity")
        weather_desc = FifaMatchSync._fifa_locale_desc(weather.get("TypeLocalized"))

        if temp is not None and match.temperature != temp:
            match.temperature = temp
            changed = True
        if humidity is not None and match.humidity != humidity:
            match.humidity = humidity
            changed = True
        if weather_desc and match.weather != weather_desc:
            match.weather = weather_desc
            changed = True

        for official in fifa_row.get("Officials") or []:
            if official.get("OfficialType") == 1:
                ref_name = FifaMatchSync._fifa_locale_desc(official.get("Name"))
                ref_country = official.get("IdCountry", "")
                if ref_name and match.referee_name != ref_name:
                    match.referee_name = ref_name
                    changed = True
                if ref_country and match.referee_nationality != ref_country:
                    match.referee_nationality = ref_country
                    changed = True
                break

        return changed

    @staticmethod
    async def _fetch_fifa_scores(db: AsyncSession) -> List[Dict]:
        """
        Fetch 2026 World Cup scores from FIFA calendar API.

        Uses idCompetition/idSeason so we don't pull unrelated historical events.
        """
        updates = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    FifaMatchSync.FIFA_API,
                    params={
                        "idCompetition": FIFA_COMPETITION_ID,
                        "idSeason": FIFA_SEASON_ID,
                        "language": "en",
                        "count": 500,
                    },
                    headers=FifaMatchSync.FIFA_HTTP_HEADERS,
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    print(f"[Scraper] FIFA API returned {resp.status_code}")
                    return updates

                data = resp.json()
                results = data.get("Results") or []
                print(f"[Scraper/FIFA] Fetched {len(results)} World Cup matches")

                for r in results:
                    home = r.get("Home") or {}
                    away = r.get("Away") or {}
                    home_code = home.get("IdCountry") or ""
                    away_code = away.get("IdCountry") or ""
                    fifa_match_id = str(r.get("IdMatch", ""))

                    home_name = FifaMatchSync._fifa_locale_desc(home.get("TeamName")) or "TBD"
                    away_name = FifaMatchSync._fifa_locale_desc(away.get("TeamName")) or "TBD"
                    fifa_dt = FifaMatchSync._parse_fifa_datetime(r.get("Date", ""))

                    match = await FifaMatchSync._find_match_by_fifa_id(db, fifa_match_id)
                    swap_scores = False
                    if not match and home_code and away_code:
                        match = await FifaMatchSync._find_match_by_fifa_codes(
                            db, home_code, away_code, fifa_dt
                        )
                        if not match:
                            match = await FifaMatchSync._find_match_by_fifa_codes(
                                db, away_code, home_code, fifa_dt
                            )
                            swap_scores = match is not None

                    if not match:
                        if home_code or away_code:
                            print(
                                f"[Scraper/FIFA] No DB match for "
                                f"{home_name} vs {away_name} ({home_code}-{away_code})"
                            )
                        continue

                    teams_changed = await FifaMatchSync._sync_fifa_teams(
                        db, match, home_code, away_code
                    )
                    metadata_changed = FifaMatchSync._sync_fifa_match_metadata(match, r)
                    if teams_changed or metadata_changed:
                        await db.flush()

                    raw_status = r.get("MatchStatus", 1)
                    status = FifaMatchSync.FIFA_STATUS_MAP.get(raw_status, "scheduled")
                    home_score = r.get("HomeTeamScore")
                    away_score = r.get("AwayTeamScore")

                    if home_score is None and away_score is None:
                        if teams_changed or metadata_changed:
                            await db.commit()
                        continue

                    if swap_scores and home_score is not None and away_score is not None:
                        home_score, away_score = away_score, home_score

                    print(
                        f"[Scraper/FIFA] {home_name} {home_score}-{away_score} "
                        f"{away_name} ({status})"
                    )

                    prev = (match.home_score, match.away_score, match.status)
                    await FifaMatchSync._update_match_score(
                        db, match, home_score, away_score, status
                    )
                    if (match.home_score, match.away_score, match.status) != prev:
                        updates.append({
                            "match_id": match.id,
                            "home_score": home_score,
                            "away_score": away_score,
                            "status": status,
                        })

        except Exception as e:
            print(f"[Scraper] FIFA API error: {e}")

        return updates

    @staticmethod
    def _parse_embedded_json(html: str) -> Optional[dict]:
        """Parse __INITIAL_STATE__ JSON from Dongqiudi HTML."""
        try:
            start = html.find("window.__INITIAL_STATE__=")
            if start == -1:
                return None
            start = html.find("{", start)
            if start == -1:
                return None

            depth = 0
            end = start
            for i in range(start, len(html)):
                if html[i] == "{":
                    depth += 1
                elif html[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            json_str = html[start:end]
            return json.loads(json_str)
        except Exception:
            return None

    @staticmethod
    def _extract_scores(data: dict) -> List[Dict]:
        """Extract match scores from Dongqiudi data structure."""
        updates = []
        try:
            # Dongqiudi structure varies; try common paths
            matches_data = (
                data.get("matchList") or
                data.get("matches") or
                data.get("scheduleData", {}).get("matches") or
                []
            )

            for m in matches_data:
                home_score = m.get("home_score") or m.get("score_a")
                away_score = m.get("away_score") or m.get("score_b")
                status = m.get("status") or m.get("match_status", "scheduled")

                # Map Dongqiudi status codes
                if status in ("live", "playing", "1", 1):
                    status = "live"
                elif status in ("finished", "ft", "3", 3):
                    status = "finished"
                else:
                    status = "scheduled"

                updates.append({
                    "dongqiudi_id": m.get("id") or m.get("match_id"),
                    "home_score": home_score,
                    "away_score": away_score,
                    "status": status,
                    "home_team_name": m.get("team_A_name") or m.get("home_team"),
                    "away_team_name": m.get("team_B_name") or m.get("away_team"),
                })
        except Exception as e:
            print(f"[Scraper] Score extraction error: {e}")

        return updates

    @staticmethod
    async def _apply_score_update(db: AsyncSession, update: Dict):
        """Apply a score update to the database."""
        # Try to find match by team names
        home_name = update.get("home_team_name", "")
        away_name = update.get("away_team_name", "")

        if home_name and away_name:
            result = await db.execute(
                select(Match)
                .options(selectinload(Match.home_team), selectinload(Match.away_team))
                .where(Match.status.in_(["scheduled", "live"]))
            )
            matches = result.scalars().all()

            for m in matches:
                if (m.home_team.name_cn == home_name and
                    m.away_team.name_cn == away_name):
                    await FifaMatchSync._update_match_score(
                        db, m, update["home_score"],
                        update["away_score"], update["status"]
                    )
                    break

    @staticmethod
    async def _update_match_score(db: AsyncSession, match: Match,
                                   home_score: int, away_score: int, status: str):
        """Update match score and trigger downstream updates."""
        if match.home_score == home_score and match.away_score == away_score and match.status == status:
            return  # No change

        match.home_score = home_score
        match.away_score = away_score
        match.status = status
        await db.flush()

        print(f"[Scraper] Updated: {match.home_team.name_cn} {home_score}-{away_score} {match.away_team.name_cn}")

        # If match finished, run full settlement pipeline
        if status == "finished":
            from app.services.match_settlement import settle_finished_match
            await settle_finished_match(db, match, home_score, away_score)
            print("[FifaMatchSync] Match settled: Elo, bets, predictions updated")
        else:
            await db.commit()

    @staticmethod
    async def fetch_injury_news(db: AsyncSession) -> List[Dict]:
        """Search for latest injury news from Dongqiudi."""
        injuries = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{FifaMatchSync.API_BASE}/global/2026-worldcup",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    text = resp.text
                    keywords = ["伤病", "受伤", "伤缺", "缺席", "injury", "injured"]
                    for kw in keywords:
                        if kw in text.lower():
                            idx = text.lower().find(kw.lower())
                            snippet = text[max(0, idx-100):idx+200]
                            injuries.append({"keyword": kw, "snippet": snippet[:150]})
        except Exception as e:
            print(f"[Scraper] Injury fetch failed: {e}")

        return injuries

    @staticmethod
    async def manual_score_update(db: AsyncSession, match_id: int,
                                   home_score: int, away_score: int) -> Dict:
        """Manual score update via admin panel."""
        result = await db.execute(
            select(Match).options(
                selectinload(Match.home_team), selectinload(Match.away_team)
            ).where(Match.id == match_id)
        )
        match = result.scalar_one_or_none()
        if not match:
            return {"error": "Match not found"}

        await FifaMatchSync._update_match_score(
            db, match, home_score, away_score, "finished"
        )
        return {"status": "ok", "match_id": match_id}


# Backward-compatible alias
DongqiudiScraper = FifaMatchSync
