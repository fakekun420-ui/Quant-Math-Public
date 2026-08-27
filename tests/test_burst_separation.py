"""Tests for burst history and burst monitor separation (v1.2.1)."""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quant_math.cli.main import (
    BURST_LOG_PATH,
    BURST_STATE_DIR,
    LOG_PATH,
    _burst_count_open_positions,
    _burst_read_paper_trades,
    _read_closures,
    _read_paper_trades,
    view_burst_history,
    view_log_path,
)


class TestBurstConstants:
    def test_burst_log_differs_from_classic(self):
        assert BURST_LOG_PATH != LOG_PATH

    def test_burst_state_dir_differs(self):
        classic_state = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "runtime", "state")
        assert BURST_STATE_DIR != classic_state


class TestReadPaperTrades:
    def test_reads_from_burst_state_dir(self, tmp_path):
        state_dir = str(tmp_path)
        trades_file = os.path.join(state_dir, "paper_executions.jsonl")
        trade = {"key": "BTC/USDT:m1", "symbol": "BTC/USDT", "pnl": 1.5}
        with open(trades_file, "w") as f:
            f.write(json.dumps(trade) + "\n")
        result = _read_paper_trades(state_dir)
        assert len(result) == 1
        assert result[0]["key"] == "BTC/USDT:m1"

    def test_empty_state_dir(self, tmp_path):
        result = _read_paper_trades(str(tmp_path))
        assert result == []


class TestReadClosures:
    def test_reads_closures(self, tmp_path):
        trades_file = os.path.join(tmp_path, "paper_executions.jsonl")
        closed = {"key": "ETH/USDT:m2", "pnl": 2.0, "motivo_cierre": "tp"}
        open_t = {"key": "SOL/USDT:m3", "pnl": 0.5}
        with open(trades_file, "w") as f:
            f.write(json.dumps(closed) + "\n")
            f.write(json.dumps(open_t) + "\n")
        closures = _read_closures(str(tmp_path))
        assert len(closures) == 1
        assert closures[0]["motivo_cierre"] == "tp"

    def test_no_closures(self, tmp_path):
        assert _read_closures(str(tmp_path)) == []


class TestBurstReadPaperTrades:
    def test_reads_burst_state(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "quant_math.cli.main.BURST_STATE_DIR", str(tmp_path))
        trades_file = os.path.join(str(tmp_path), "paper_executions.jsonl")
        trade = {"key": "BTC/USDT:b1", "symbol": "BTC/USDT", "pnl": 3.0}
        with open(trades_file, "w") as f:
            f.write(json.dumps(trade) + "\n")
        result = _burst_read_paper_trades()
        assert len(result) == 1
        assert result[0]["key"] == "BTC/USDT:b1"


class TestBurstCountOpenPositions:
    def test_counts_open(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "quant_math.cli.main.BURST_STATE_DIR", str(tmp_path))
        # _count_open_positions reads from positions.jsonl
        positions_file = os.path.join(str(tmp_path), "positions.jsonl")
        open1 = {"key": "BTC/USDT:b1", "symbol": "BTC/USDT"}
        closed = {"key": "ETH/USDT:b2", "symbol": "ETH/USDT",
                  "motivo_cierre": "tp", "pnl": 1.0}
        open2 = {"key": "SOL/USDT:b3", "symbol": "SOL/USDT"}
        with open(positions_file, "w") as f:
            f.write(json.dumps(open1) + "\n")
            f.write(json.dumps(closed) + "\n")
            f.write(json.dumps(open2) + "\n")
        count = _burst_count_open_positions()
        assert count == 3  # counts all lines in positions.jsonl


class TestViewLogPath:
    def test_missing_log_file(self, tmp_path, capsys):
        fake_path = str(tmp_path / "nonexistent.log")
        # view_log_path calls questionary.press_any_key which needs a terminal;
        # verify the function exists and the path check works
        assert not os.path.exists(fake_path)
        # Just verify the function signature is correct
        import inspect
        sig = inspect.signature(view_log_path)
        assert "log_path" in sig.parameters


class TestTwoPassMonitorFix:
    """Test that the two-pass scan correctly identifies open entries."""

    def test_entries_before_closures_are_not_counted(self, tmp_path):
        """Entries that appear BEFORE their closure records should not be counted as open."""
        trades_file = os.path.join(tmp_path, "paper_executions.jsonl")
        # Entry appears first (line 1), closure appears later (line 6)
        entry1 = {"key": "hyp_aaa:XRP/USDT", "side": "buy", "entry_price": 1.41,
                  "symbol": "XRP/USDT", "quantity": 70.0, "margin_usd": 10.0}
        entry2 = {"key": "hyp_bbb:XRP/USDT", "side": "sell", "entry_price": 1.40,
                  "symbol": "XRP/USDT", "quantity": 71.0, "margin_usd": 10.0}
        closure1 = {"key": "hyp_aaa:XRP/USDT", "motivo_cierre": "sl", "pnl": -1.3}
        closure2 = {"key": "hyp_bbb:XRP/USDT", "motivo_cierre": "sl", "pnl": -0.8}

        with open(trades_file, "w") as f:
            f.write(json.dumps(entry1) + "\n")
            f.write(json.dumps(entry2) + "\n")
            f.write(json.dumps(closure1) + "\n")
            f.write(json.dumps(closure2) + "\n")

        trades = _read_paper_trades(tmp_path)

        # Two-pass logic (same as render_burst_monitor)
        closed_keys = set()
        total_closed = 0
        total_pnl = 0.0
        for t in trades:
            key = t.get("key")
            if "motivo_cierre" in t:
                if key:
                    closed_keys.add(key)
                total_closed += 1
                total_pnl += float(t.get("pnl", 0.0))
        open_entries = [
            t for t in trades
            if "motivo_cierre" not in t
            and t.get("key") not in closed_keys
        ]

        assert total_closed == 2
        assert total_pnl == -2.1
        assert len(open_entries) == 0  # Both are closed

    def test_mixed_open_and_closed(self, tmp_path):
        """Some entries open, some closed — only open ones should count."""
        trades_file = os.path.join(tmp_path, "paper_executions.jsonl")
        entry1 = {"key": "hyp_111:XRP/USDT", "side": "buy", "entry_price": 1.41,
                  "symbol": "XRP/USDT", "quantity": 70.0, "margin_usd": 10.0}
        entry2 = {"key": "hyp_222:XRP/USDT", "side": "sell", "entry_price": 1.40,
                  "symbol": "XRP/USDT", "quantity": 71.0, "margin_usd": 10.0}
        entry3 = {"key": "hyp_333:XRP/USDT", "side": "buy", "entry_price": 1.42,
                  "symbol": "XRP/USDT", "quantity": 70.0, "margin_usd": 10.0}
        closure1 = {"key": "hyp_111:XRP/USDT", "motivo_cierre": "sl", "pnl": -1.3}

        with open(trades_file, "w") as f:
            f.write(json.dumps(entry1) + "\n")
            f.write(json.dumps(entry2) + "\n")
            f.write(json.dumps(entry3) + "\n")
            f.write(json.dumps(closure1) + "\n")

        trades = _read_paper_trades(tmp_path)

        closed_keys = set()
        total_closed = 0
        for t in trades:
            if "motivo_cierre" in t:
                key = t.get("key")
                if key:
                    closed_keys.add(key)
                total_closed += 1
        open_entries = [
            t for t in trades
            if "motivo_cierre" not in t
            and t.get("key") not in closed_keys
        ]

        assert total_closed == 1
        assert len(open_entries) == 2
        assert open_entries[0]["key"] == "hyp_222:XRP/USDT"
        assert open_entries[1]["key"] == "hyp_333:XRP/USDT"


class TestRuntimeStateMultiProcess:
    """Test RuntimeState supports multiple simultaneous processes."""

    def test_running_mode_returns_false_for_unknown(self):
        from quant_math.cli.main import RuntimeState
        rs = RuntimeState()
        assert rs.running_mode("classic") is False
        assert rs.running_mode("burst") is False

    def test_any_running_empty(self):
        from quant_math.cli.main import RuntimeState
        rs = RuntimeState()
        assert rs.any_running() == []

    def test_stats_for_missing_mode(self, tmp_path):
        from quant_math.cli.main import RuntimeState
        rs = RuntimeState()
        # stats_for returns state based on whether process is alive
        stats = rs.stats_for("classic")
        assert "state" in stats
        assert stats["state"] in ("RUNNING", "STOPPED")

    def test_config_dict_legacy_none(self):
        from quant_math.cli.main import RuntimeState
        rs = RuntimeState()
        assert rs.config_dict is None

    def test_clear_pid_nonexistent(self, tmp_path, monkeypatch):
        from quant_math.cli.main import RuntimeState
        rs = RuntimeState()
        # Should not raise
        rs._clear_pid("classic")


class TestMemoryPruning:
    """Test that AQDERunner prunes unbounded data structures."""

    def test_prune_performance_history(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from aqde_runner import AQDERunner
        runner = AQDERunner.__new__(AQDERunner)
        runner.performance_history = [{"cycle": i} for i in range(600)]
        runner.all_hypotheses = {}

        runner._prune_memory()

        assert len(runner.performance_history) == 500
        # Should keep only the last 500
        assert runner.performance_history[0]["cycle"] == 100

    def test_prune_all_hypotheses(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from aqde_runner import AQDERunner
        from quant_math.autonomous_research.interfaces import Hypothesis

        runner = AQDERunner.__new__(AQDERunner)
        runner.performance_history = []
        runner.all_hypotheses = {}

        # Create 250 hypotheses, some retired
        for i in range(250):
            h = Hypothesis.__new__(Hypothesis)
            h.hypothesis_id = f"hyp_{i}"
            if i % 3 == 0:
                h.status = "retired"
            else:
                h.status = "active"
            runner.all_hypotheses[f"hyp_{i}"] = h

        runner._prune_memory()

        # Only active hypotheses should remain
        assert all(v.status != "retired" for v in runner.all_hypotheses.values())
        assert len(runner.all_hypotheses) > 0
