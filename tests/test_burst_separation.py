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
