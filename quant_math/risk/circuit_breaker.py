"""
Circuit breaker diario: tope de DANO por dia, drawdown y posiciones.

Que bloquea y que no
--------------------
Este guard BLOQUEA entradas nuevas. Los cierres (`check_exits_all`) se
ejecutan ANTES y siguen ejecutandose: un tope de perdida nunca deja de
gestionar el riesgo que ya esta abierto, solo deja de añadir mas.

OJO CON EL NOMBRE (correccion no3, 2026-09-29): `max_daily_loss_usd` limita
el DANO POR DIA, NO el numero de operaciones. El paper es ilimitado en
tiempo (decision de Leonardo): se puede operar toda la noche, pero si el
dia se vuelve negativo se deja de abrir. Leerlo al reves lleva a creer que
existe un tope de frecuencia, que no existe.

Que mira (los tres numeros que se comparan)
-------------------------------------------
1. DANO DEL DIA = `realized_today + min(0, unrealized_today)`.
   Se suma el flotante NEGATIVO del dia porque una posicion abierta en
   contra ya es dano: sin ella, 5 posiciones perdedoras dan 0,00% de
   perdida y el guard dice PERMITE (medido, F3 2026-09-29).
   El flotante se reparte asi:
     - `unrealized_today`  -> posiciones abiertas DESDE las 00:00 UTC
       (el dano de HOY).
     - `unrealized_total`  -> todas las vivas; entra en el `equity` y por
       tanto en el drawdown, que es la red que agarra las posiciones
       viejas que siguen sangrando.
2. DRAWDOWN = (peak_equity - equity) / peak_equity, con `equity` marcado:
   capital inicial + PnL realizado + PnL NO REALIZADO.
3. POSICIONES SIMULTANEAS >= `max_open_positions`.

Falla cerrado
-------------
`unpriced_positions` son posiciones vivas que NO se han podido marcar
(sin precio, o sin tamano en el libro). Un PnL que no se puede calcular no
se puede_CALLAR_: se cuenta como no marcado y, si supera la tolerancia,
se bloquean las entradas. Es la misma politica que `_apply_margin_cap`.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

#: Tope de DANO por dia como fraccion del capital. 5% = la mitad del
#: peor dia posible con los topes del resto del sistema:
#: `max_risk_per_trade_pct` (2% por operacion) x `max_open_positions` (5)
#: = 10% de capital si todas las posiciones abiertas tocan el SL a la vez.
#: Con este tope el dia se PARA cuando ya se ha gastado la mitad de ese
#: peor caso, no cuando ya se ha perdido el 10% entero.
DEFAULT_MAX_DAILY_LOSS_PCT: float = 0.05

#: Compatibilidad historica: 2,50 USD era el tope de la cuenta de 50 USD del
#: run paper (5% de 50). Se conserva como valor por defecto cuando la
#: config NO pasa porcentaje.
DEFAULT_MAX_DAILY_LOSS_USD: float = 2.5


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def utc_day_start_ts() -> float:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


def daily_loss_usd(capital: float, pct: float) -> float:
    """Traduce el tope de dano diario en % a USD sobre el capital."""
    return max(0.0, float(capital) * float(pct))


class DailyGuard:
    """Persistent daily-loss / drawdown / exposure circuit breaker."""

    FILENAME = "daily_pnl.json"

    def __init__(self, state_dir: str,
                 max_daily_loss_usd: float = DEFAULT_MAX_DAILY_LOSS_USD,
                 max_open_positions: int = 5,
                 drawdown_limit: float = 0.2):
        self.state_dir = state_dir
        self.path = os.path.join(state_dir, self.FILENAME)
        self.max_daily_loss_usd = max(0.0, float(max_daily_loss_usd))
        self.max_open_positions = max(1, int(max_open_positions))
        self.drawdown_limit = max(0.0, float(drawdown_limit))
        #: Tope de posiciones vivas que se pueden quedar SIN marcar antes
        #: de bloquear entradas. 0 = ninguna tolerancia (falla cerrado).
        self.max_unpriced_positions = 0
        #: Ultima lectura, para el informe/stats del orquestador.
        self.last = {}

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

    def snapshot(self, realized_today: float, equity: float,
                 unrealized_today: float = 0.0,
                 unrealized_total: float = 0.0,
                 unpriced_positions: int = 0) -> Dict:
        """Persist today's reading (rolls over at UTC midnight).

        `equity` llega YA marcado (incluye flotante): el pico se guarda
        sobre esa cifra, que es la que significa algo para el drawdown.
        """
        today = utc_today()
        prev = self._load()
        if prev.get("date") == today:
            peak = max(float(prev.get("peak_equity", equity)), equity)
        else:
            peak = equity
        data = {
            "date": today,
            "realized_today": round(realized_today, 10),
            "unrealized_today": round(unrealized_today, 10),
            "unrealized_total": round(unrealized_total, 10),
            "unpriced_positions": int(unpriced_positions),
            "equity": round(equity, 10),
            "peak_equity": round(peak, 10),
            "max_daily_loss_usd": self.max_daily_loss_usd,
            "max_open_positions": self.max_open_positions,
            "drawdown_limit": self.drawdown_limit,
            "updated_at": time.time(),
        }
        self._save(data)
        self.last = data
        return data

    # ------------------------------------------------------------------
    # Checks — return (ok, reason); ok=False means BLOCK new entries
    # ------------------------------------------------------------------

    def check(self, realized_today: float, equity: float,
              open_count: int, unrealized_today: float = 0.0,
              unrealized_total: float = 0.0,
              unpriced_positions: int = 0) -> Tuple[bool, Optional[str]]:
        snap = self.snapshot(realized_today, equity,
                             unrealized_today=unrealized_today,
                             unrealized_total=unrealized_total,
                             unpriced_positions=unpriced_positions)
        peak = snap["peak_equity"]
        # El flotante SOLO resta: una ganancia no realizada no paga
        # deudas, y asi el dano de hoy nunca se maquilla al alza.
        float_today = min(0.0, float(unrealized_today or 0.0))
        day_pnl = float(realized_today or 0.0) + float_today

        if unpriced_positions > self.max_unpriced_positions:
            return False, (
                f"{int(unpriced_positions)} posicion(es) abierta(s) sin "
                f"marcar (precio o tamano no disponibles) > "
                f"tolerancia {self.max_unpriced_positions} — no se puede "
                f"medir el riesgo: entries blocked"
            )
        if day_pnl <= -self.max_daily_loss_usd:
            realized_txt = f"{float(realized_today or 0.0):+.2f}"
            float_txt = f"{float_today:+.2f}"
            return False, (
                f"daily loss {day_pnl:+.2f} <= -{self.max_daily_loss_usd:.2f} "
                f"(max_daily_loss_usd; realizado {realized_txt} + flotante "
                f"{float_txt}) — TOPE DE DANO DEL DIA, no de operaciones: "
                f"entries blocked rest of UTC day"
            )
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > self.drawdown_limit:
                return False, (
                    f"drawdown {dd:.2%} > {self.drawdown_limit:.0%} "
                    f"(peak {peak:.2f}, equity marcado {equity:.2f}) — "
                    f"entries blocked"
                )
        if open_count >= self.max_open_positions:
            return False, (
                f"open positions {open_count} >= max {self.max_open_positions} "
                f"— entries blocked"
            )
        return True, None
