"""Tests for badge generation."""

import json
import tempfile
from pathlib import Path

from mcpbr.badges import generate_badges_from_results, get_badge_color


class TestBadgeColors:
    """Badge color thresholds."""

    def test_green_for_50_percent_or_above(self):
        assert get_badge_color(0.5) == "brightgreen"
        assert get_badge_color(0.75) == "brightgreen"
        assert get_badge_color(1.0) == "brightgreen"

    def test_yellow_for_30_to_50_percent(self):
        assert get_badge_color(0.3) == "yellow"
        assert get_badge_color(0.49) == "yellow"

    def test_red_below_30_percent(self):
        assert get_badge_color(0.0) == "red"
        assert get_badge_color(0.1) == "red"
        assert get_badge_color(0.29) == "red"


class TestGenerateBadgesFromResults:
    """generate_badges_from_results reads JSON and returns badge markdown list."""

    def test_returns_badge_markdown(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        badges = generate_badges_from_results(results)
        assert isinstance(badges, list)
        assert len(badges) >= 2  # At least resolution rate and benchmark badges

    def test_badge_uses_shields_io_format(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        badges = generate_badges_from_results(results)
        for badge in badges:
            assert "img.shields.io/badge" in badge
            assert badge.startswith("![")

    def test_badge_color_reflects_rate(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        badges = generate_badges_from_results(results)
        # High resolution (80%) should have green badge
        resolution_badge = [b for b in badges if "Resolution" in b or "80" in b][0]
        assert "brightgreen" in resolution_badge

    def test_reads_from_json_file(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.json"
            path.write_text(json.dumps(results))

            data = json.loads(path.read_text())
            badges = generate_badges_from_results(data)
            assert len(badges) >= 2

    def test_includes_benchmark_badge(self):
        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
                "baseline": {"resolved": 3, "total": 10, "rate": 0.3, "total_cost": 5.00},
            },
        }
        badges = generate_badges_from_results(results)
        benchmark_badges = [b for b in badges if "humaneval" in b.lower()]
        assert len(benchmark_badges) >= 1
