"""Test suite for world-cup-for-math."""
import json
import pytest

from app.geo import city_to_host_country
from app.services.elo import EloService
from app.services.odds_parser import OddsParser
from app.services.bet_optimizer import _match_winner


def test_city_to_host_country():
    assert city_to_host_country("Los Angeles") == "USA"
    assert city_to_host_country("Mexico City") == "MEX"
    assert city_to_host_country("Toronto") == "CAN"


def test_home_bonus_uses_country_not_city():
    bonus = EloService.get_home_bonus(
        True, "USA", city_to_host_country("Los Angeles"), "CONCACAF"
    )
    assert bonus == 100.0


def test_draw_elo_symmetric():
    a, b = EloService.update_elo_draw(1600.0, 1600.0)
    assert a == b


def test_kelly_positive_edge():
    from app.services.bet_optimizer import BetOptimizer
    k = BetOptimizer._kelly_fraction(0.55, 2.0, 0.25)
    assert k > 0


def test_match_winner():
    assert _match_winner(2, 1) == "主胜"
    assert _match_winner(1, 2) == "客胜"
    assert _match_winner(0, 0) == "平局"


def test_odds_parser_missing_file():
    OddsParser._real_odds = None
    data = OddsParser.load_real_odds()
    assert "matches" in data


def test_implied_probability_sums_to_one():
    imp = OddsParser.implied_probability(2.0, 3.2, 3.8)
    assert abs(sum(imp.values()) - 1.0) < 0.01


def test_fifa_status_map():
    from app.services.scraper import FifaMatchSync
    assert FifaMatchSync.FIFA_STATUS_MAP[0] == "finished"
    assert FifaMatchSync.FIFA_STATUS_MAP[3] == "live"
