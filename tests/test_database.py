import pytest
from backend.app.database import (
    init_db, save_project_to_db, load_project_from_db,
    save_domain_edits_db, get_domain_edits_db
)
from backend.app.services.split_io import parse_split_project
from backend.app.services.replan_engine import run_replan_calculation


def test_database_roundtrip_platea():
    init_db()
    orig = parse_split_project("backend/data/projects/platea")
    save_project_to_db("platea", orig)

    from_db = load_project_from_db("platea")
    assert from_db is not None
    assert len(from_db["budget_items"]) == len(orig["budget_items"])
    assert len(from_db["tasks"]) == len(orig["tasks"])
    assert len(from_db["all_links"]) == len(orig["all_links"])

    res_orig = run_replan_calculation(orig)
    res_db = run_replan_calculation(from_db)

    assert res_orig["total_budget"] == res_db["total_budget"]
    assert res_orig["total_measured"] == res_db["total_measured"]
    assert res_orig["s_curve"]["replan_accum_pcts"] == res_db["s_curve"]["replan_accum_pcts"]


def test_database_edits_roundtrip():
    init_db()
    edits = {"schedule_overrides": {"561": {"duration": 15, "start_date": "2027-02-01"}}}
    save_domain_edits_db("platea", "cronograma", "atual", edits)

    loaded = get_domain_edits_db("platea", "cronograma", "atual")
    assert loaded == edits

    # Emptying edits should clear
    save_domain_edits_db("platea", "cronograma", "atual", {})
    cleared = get_domain_edits_db("platea", "cronograma", "atual")
    assert cleared == {}
