"""Seed validation tests."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "seed"


def test_group_schedule_has_72_unique_fifa_ids():
    data = json.loads((SEED_DIR / "group_schedule.json").read_text(encoding="utf-8"))
    matches = data["matches"]
    assert len(matches) == 72
    ids = [m["fifa_match_id"] for m in matches]
    assert len(set(ids)) == 72
    assert all(ids)


def test_group_schedule_teams_in_groups_json():
    groups = {g["name"]: set(g["teams"]) for g in json.loads((SEED_DIR / "groups.json").read_text())}
    all_teams = set()
    for teams in groups.values():
        all_teams |= teams
    data = json.loads((SEED_DIR / "group_schedule.json").read_text(encoding="utf-8"))
    for m in data["matches"]:
        assert m["home"] in all_teams
        assert m["away"] in all_teams
        assert m["group"] in groups
        assert m["home"] in groups[m["group"]]
        assert m["away"] in groups[m["group"]]


def test_knockout_schedule_count():
    data = json.loads((SEED_DIR / "knockout_schedule.json").read_text(encoding="utf-8"))
    assert len(data["matches"]) == 32
