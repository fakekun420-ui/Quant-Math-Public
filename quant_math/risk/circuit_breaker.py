"""
Daily circuit breaker for live/paper trading.

Enforces, per state_dir (i.e. per mode):
- max_daily_loss_usd: block new entries for the rest of the UTC day once
  realized daily PnL <= -max_daily_loss_usd (default $2.50 = 5% of $50).
- drawdown_limit: block new entries while (peak - equity)/peak > limit,
  where equity = initial_capital + all-time realized PnL.
- max_open_positions: block new entries while open positions >= limit.

State persists in <state_dir>/daily_pnl.json so restarts keep the guard.
Breaches only BLOCK entries — monitoring cycles continue, exits still run.

NOTE: guard uses realized PnL only (no mark-to-market of open positions),
so it is conservative in one direction: open bleed does not trigger it.
Unrealized-aware halt is a Fase-4 improvement.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def utc_day_start_ts() -> float:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


class DailyGuard:
    """Persistent daily-loss / drawdown / exposure circuit breaker."""

    FILENAME = "daily_pnl.json"

    def __init__(self, state_dir: str,
                 max_daily_loss_usd: float = 2.5,
                 max_open_positions: int = 5,
                 drawdown_limit: float = 0.2):
        self.state_dir = state_dir
        self.path = os.path.join(state_dir, self.FILENAME)
        self.max_daily_loss_usd = max(0.0, float(max_daily_loss_usd))
        self.max_open_positions = max(1, int(max_open_positions))
        self.drawdown_limit = max(0.0, float(drawdown_limit))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict) and "date" in d:
                return d
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save(self, data: Dict) -> None:
        try:
            os.makedirs(self.state_dir, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def snapshot(self, realized_today: float, equity: float) -> Dict:
        """Persist today's reading (rolls over at UTC midnight)."""
        today = utc_today()
        prev = self._load()
        if prev.get("date") == today:
            peak = max(float(prev.get("peak_equity", equity)), equity)
        else:
            peak = equity
        data = {
            "date": today,
            "realized_today": round(realized_today, 10),
            "equity": round(equity, 10),
            "peak_equity": round(peak, 10),
            "updated_at": time.time(),
        }
        self._save(data)
        return data

    # ------------------------------------------------------------------
    # Checks — return (ok, reason); ok=False means BLOCK new entries
    # ------------------------------------------------------------------

    def check(self, realized_today: float, equity: float,
              open_count: int) -> Tuple[bool, Optional[str]]:
        snap = self.snapshot(realized_today, equity)
        peak = snap["peak_equity"]

        if realized_today <= -self.max_daily_loss_usd:
            return False, (
                f"daily loss {realized_today:+.2f} <= -{self.max_daily_loss_usd:.2f} "
                f"(max_daily_loss_usd) — entries blocked rest of UTC day"
            )
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > self.drawdown_limit:
                return False, (
                    f"drawdown {dd:.2%} > {self.drawdown_limit:.0%} "
                    f"(peak {peak:.2f}, equity {equity:.2f}) — entries blocked"
                )
        if open_count >= self.max_open_positions:
            return False, (
                f"open positions {open_count} >= max {self.max_open_positions} "
                f"— entries blocked"
            )
        return True, None
