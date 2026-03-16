"""Tests for the cost tracker."""

from pathlib import Path

from homeclaw.agent.cost_tracker import CostTracker, estimate_cost, load_prices


def test_load_prices():
    prices = load_prices()
    assert "claude-sonnet-4-6" in prices
    assert prices["claude-sonnet-4-6"].input_per_mtok == 3.0


def test_estimate_cost_basic():
    prices = load_prices()
    # 1000 input tokens, 100 output tokens, no cache, sonnet
    cost = estimate_cost("claude-sonnet-4-6", 1000, 100, 0, prices)
    expected = (1000 / 1_000_000) * 3.0 + (100 / 1_000_000) * 15.0
    assert abs(cost - expected) < 1e-8


def test_estimate_cost_with_cache():
    prices = load_prices()
    cost = estimate_cost("claude-sonnet-4-6", 1000, 100, 800, prices)
    # 200 uncached input + 800 cached + 100 output
    expected = (
        (200 / 1_000_000) * 3.0
        + (800 / 1_000_000) * 0.30
        + (100 / 1_000_000) * 15.0
    )
    assert abs(cost - expected) < 1e-8


def test_estimate_cost_with_provider_prefix():
    prices = load_prices()
    cost = estimate_cost("anthropic/claude-sonnet-4-6", 1000, 100, 0, prices)
    assert cost > 0


def test_estimate_cost_unknown_model():
    prices = load_prices()
    assert estimate_cost("unknown-model", 1000, 100, 0, prices) == 0.0


def test_tracker_log_and_read(tmp_path: Path):
    tracker = CostTracker(tmp_path)
    tracker.log("conversation", "claude-sonnet-4-6", 1000, 200, "alice")
    tracker.log("routine", "claude-haiku-4-5-20251001", 500, 100, "household")

    entries = tracker.read_entries(days=1)
    assert len(entries) == 2
    assert entries[0].call_type == "conversation"
    assert entries[0].person == "alice"
    assert entries[1].call_type == "routine"


def test_tracker_cost_is_calculated(tmp_path: Path):
    tracker = CostTracker(tmp_path)
    entry = tracker.log("conversation", "claude-sonnet-4-6", 1000, 200, "alice")
    assert entry.estimated_cost_usd > 0


def test_tracker_empty_read(tmp_path: Path):
    tracker = CostTracker(tmp_path)
    assert tracker.read_entries() == []
