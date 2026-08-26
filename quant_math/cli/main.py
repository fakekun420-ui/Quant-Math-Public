"""
Quant-Math interactive CLI.

Menu:
  1. Iniciar Quant-Math       -> config wizard, then Orchestrator in a background PROCESS
  2. Detener investigación    -> graceful stop of the background process
  3. Monitor                  -> live rich dashboard (if running)
  4. Ver log                  -> paginated quant_math.log viewer
  5. Historial de operaciones -> trade history viewer
  6. Iniciar Burst Scalping   -> burst mode wizard (scalp bursts, $10 margin × leverage)
  7. Salir

Logs from the orchestrator process go to quant_math.log ONLY — they never
mix with the Live monitor render.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing as mp
import os
import signal
import socket
import subprocess
import sys
import time
from typing import Dict, Optional

import questionary
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_PATH = os.path.join(PROJECT_ROOT, "quant_math.log")
BURST_LOG_PATH = os.path.join(PROJECT_ROOT, "quant_math_burst.log")
BURST_STATE_DIR = os.path.join(PROJECT_ROOT, "runtime", "state_burst")

console = Console()


# ---------------------------------------------------------------------------
# Background process target (module-level so it is picklable)
# ---------------------------------------------------------------------------

def _orchestrator_process_main(cfg_dict: Dict):
    """Child process: run the orchestrator loop with all output to quant_math.log."""
    log_path = cfg_dict.get("log_path", LOG_PATH)
    # Route ALL stdout/stderr to the log file before importing heavy modules
    class _CappedStream:
        """stdout del hijo con techo de tamano: rota a .1 al superar max_mb."""

        def __init__(self, path, max_mb=150):
            self.path = path
            self.max_bytes = int(max_mb * 1024 * 1024)
            self.fh = open(path, "a", buffering=1)

        def write(self, data):
            try:
                if self.fh.tell() > self.max_bytes:
                    self.fh.close()
                    bak = self.path + ".1"
                    if os.path.exists(bak):
                        os.remove(bak)
                    os.replace(self.path, bak)
                    self.fh = open(self.path, "a", buffering=1)
            except OSError:
                pass
            return self.fh.write(data)

        def flush(self):
            try:
                self.fh.flush()
            except OSError:
                pass

    cap = _CappedStream(log_path, max_mb=150)
    sys.stdout = cap
    sys.stderr = cap
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[RotatingFileHandler(log_path, maxBytes=100 * 1024 * 1024,
                                      backupCount=3)],
        force=True,
    )

    def _handle_sigint(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handle_sigint)

    from quant_math.orchestrator import Orchestrator, OrchestratorConfig

    log_path = cfg_dict.pop("log_path", LOG_PATH)
    config = OrchestratorConfig(**cfg_dict)
    orch = Orchestrator(config)
    try:
        orch.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        orch.mark_stopped()
        cap.fh.close()


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

class RuntimeState:
    """Tracks the background orchestrator process."""

    def __init__(self):
        self.process: Optional[mp.Process] = None
        self.config_dict: Optional[Dict] = None

    @staticmethod
    def _pg_alive(timeout=1.5) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", 15432), timeout=timeout):
                return True
        except OSError:
            return False

    def _ensure_pg_vm(self):
        """Arranca la microVM de PostgreSQL si no responde; si falla, sigue
        con fallback a JSONL dejando el motivo claro en consola."""
        if os.environ.get("QUANTMATH_PG_DISABLE") == "1":
            console.print("[dim]PG deshabilitado (QUANTMATH_PG_DISABLE=1) — "
                          "KB en modo JSONL[/dim]")
            return
        if self._pg_alive():
            return
        boot = os.environ.get(
            "QUANTMATH_PG_BOOT", "/var/lib/quantmath-pgvm/boot_pg_vm.py")
        if not os.path.exists(boot):
            console.print("[yellow]PostgreSQL no disponible y no hay script "
                          f"de arranque ({boot}) — fallback a JSONL[/yellow]")
            return
        console.print("[cyan]PostgreSQL VM no responde — iniciando microVM "
                      "(puede tardar unos minutos)...[/cyan]")
        try:
            logf = open("/var/lib/quantmath-pgvm/autostart.log", "ab")
            subprocess.Popen(
                [sys.executable, "-u", boot, "normal"],
                stdin=subprocess.DEVNULL, stdout=logf, stderr=logf,
                start_new_session=True)
        except Exception as exc:
            console.print(f"[yellow]No se pudo lanzar la VM ({exc}) — "
                          "fallback a JSONL[/yellow]")
            return
        timeout_s = int(os.environ.get("QUANTMATH_PG_BOOT_TIMEOUT", "480"))
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._pg_alive():
                console.print("[green]PostgreSQL VM lista.[/green]")
                return
            time.sleep(5)
        console.print(f"[yellow]VM no respondio en {timeout_s}s — "
                      "fallback a JSONL[/yellow]")

    def _stop_pg_vm(self, timeout: float = 25.0) -> bool:
        """Apaga la microVM de PostgreSQL: 'quit' por el FIFO de control del
        driver; si el FIFO no tiene lector (driver muerto), fallback a pkill
        acotado a NUESTROS procesos. Devuelve True solo si el puerto quedo
        caido."""
        fifo = "/var/lib/quantmath-pgvm/cmd.fifo"
        sent = False
        try:
            fd = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
            try:
                os.write(fd, b"quit\n")
                sent = True
            finally:
                os.close(fd)
        except OSError:
            sent = False
        if not sent:
            subprocess.run(["pkill", "-9", "-f",
                            "/var/lib/quantmath-pgvm/boot_pg_vm.py"],
                           check=False)
            subprocess.run(["pkill", "-9", "-f",
                            "qemu-system-aarch64.*pgdata.qcow2"],
                           check=False)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._pg_alive(timeout=1.0):
                return True
            time.sleep(1.5)
        return False
    @property
    def running(self) -> bool:
        return self.process is not None and self.process.is_alive()

    @property
    def stats(self) -> Dict:
        if not self.config_dict:
            return {}
        stats_path = os.path.join(self.config_dict["state_dir"], "runtime_stats.json")
        if not os.path.exists(stats_path):
            return {"state": "RUNNING" if self.running else "STOPPED"}
        try:
            with open(stats_path) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}

    def start(self, config_dict: Dict):
        self._ensure_pg_vm()
        # Confirmado por el operador: el sistema opera a proposito con
        # perdidas iniciales para alimentar el aprendizaje (solo paper).
        os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")
        self.config_dict = config_dict
        ctx = mp.get_context("spawn")
        self.process = ctx.Process(
            target=_orchestrator_process_main,
            args=(config_dict,),
            daemon=False,
            name="quant-math-orchestrator",
        )
        self.process.start()

    def stop(self, timeout: float = 15.0) -> bool:
        """Aggressive escalating stop: SIGINT -> SIGTERM -> SIGKILL, <10s worst case."""
        if self.process is None:
            return False
        was_running = self.running
        if not was_running and self.process.exitcode is not None:
            return False
        # SpawnProcess no soporta send_signal(); usar os.kill directamente
        try:
            os.kill(self.process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        self.process.join(timeout=2)
        if self.process.is_alive():
            # Mid-network-call: SIGTERM mata inmediatamente
            self.process.terminate()
            self.process.join(timeout=2)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=3)
        self._force_stats_stopped()
        return True

    def _force_stats_stopped(self):
        """Best-effort: reflect STOPPED in runtime_stats.json."""
        if not self.config_dict:
            return
        stats_path = os.path.join(self.config_dict["state_dir"], "runtime_stats.json")
        try:
            if os.path.exists(stats_path):
                with open(stats_path) as fh:
                    data = json.load(fh)
                if data.get("state") != "STOPPED":
                    data["state"] = "STOPPED"
                    with open(stats_path, "w") as fh:
                        json.dump(data, fh, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError):
            pass


# ---------------------------------------------------------------------------
# Config wizard
# ---------------------------------------------------------------------------

def ask_float(label: str, default: str, lo: float = None, hi: float = None):
    while True:
        raw = questionary.text(f"{label}:", default=default).unsafe_ask()
        if raw is None:  # ESC -> back
            return None
        try:
            val = float(raw)
            if lo is not None and val <= lo:
                console.print(f"[red]Debe ser > {lo}[/red]")
                continue
            if hi is not None and not (0 < val <= hi):
                console.print(f"[red]Debe estar en (0, {hi}][/red]")
                continue
            return val
        except ValueError:
            console.print("[red]Número inválido[/red]")


def ask_int(label: str, default: str, lo: int = None):
    while True:
        raw = questionary.text(f"{label}:", default=default).unsafe_ask()
        if raw is None:
            return None
        try:
            val = int(raw)
            if lo is not None and val < lo:
                console.print(f"[red]Debe ser >= {lo}[/red]")
                continue
            return val
        except ValueError:
            console.print("[red]Entero inválido[/red]")


def wizard() -> Optional[Dict]:
    """Interactive configuration wizard. Returns cfg dict or None if cancelled."""
    console.print(Panel("[bold cyan]Wizard de configuración[/bold cyan]\n"
                        "Los datos de mercado son SIEMPRE reales (Bybit). "
                        "El modo es paper trading.", expand=False))
    try:
        # V2: selector interactivo Top-20 o manual
        use_top = questionary.select(
            "Selección de símbolos:",
            choices=[
                questionary.Choice("Top-20 por volumen (recomendado)",
                                   value="top20"),
                questionary.Choice("Ingresar manualmente", value="manual"),
            ]).unsafe_ask()
        if use_top is None:
            return None

        if use_top == "top20":
            console.print("[cyan]Obteniendo Top-20 por volumen...[/cyan]")
            top_assets = fetch_top_volume_assets("bybit", 20)
            try:
                _cb_result = questionary.checkbox(
                    "Selecciona símbolos (espacio marcar, Enter confirmar):",
                    choices=[questionary.Choice(s, value=s) for s in top_assets]
                ).unsafe_ask()
            except (AttributeError, TypeError):
                return None
            # questionary may return list or tuple depending on version
            if isinstance(_cb_result, tuple):
                selected = list(_cb_result[0]) if _cb_result and _cb_result[0] else []
            elif isinstance(_cb_result, list):
                selected = _cb_result
            else:
                selected = list(_cb_result) if _cb_result else []
            if not selected:
                console.print("[red]Debes seleccionar al menos un símbolo[/red]")
                return None
            symbols = selected
        else:
            symbols_raw = questionary.text(
                "Símbolos (separados por coma):",
                default="BTC/USDT").unsafe_ask()
            if symbols_raw is None:
                return None
            symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
            if not symbols:
                console.print("[red]Se requiere al menos un símbolo[/red]")
                return None

        initial_capital = ask_float("Capital inicial (USD)", "10000", lo=0)
        if initial_capital is None:
            return None
        entry_pct = ask_float("% de capital por entrada (0-1]", "0.05", hi=1)
        if entry_pct is None:
            return None
        timeframe = questionary.select(
            "Timeframe:", choices=["1m", "5m", "15m", "1h", "4h", "1d"],
            default="1h").unsafe_ask()
        if timeframe is None:
            return None
        take_profit_pct = ask_float("Take-profit % (ej. 0.02 = 2%)", "0.02")
        if take_profit_pct is None:
            return None
        lookback_days = ask_int("Lookback days (backtest)", "30", lo=1)
        if lookback_days is None:
            return None
        hypotheses_per_cycle = ask_int("Hipótesis nuevas por ciclo", "3", lo=1)
        if hypotheses_per_cycle is None:
            return None

        state_dir = os.path.join(PROJECT_ROOT, "runtime", "state")
        os.makedirs(state_dir, exist_ok=True)

        return {
            "symbols": symbols,
            "timeframe": timeframe,
            "lookback_days": lookback_days,
            "initial_capital": initial_capital,
            "entry_pct": entry_pct,
            "take_profit_pct": take_profit_pct,
            "min_paper_trades": 3,          # contract value; explicit on purpose
            "hypotheses_per_cycle": hypotheses_per_cycle,
            "kb_path": os.path.join(PROJECT_ROOT, "runtime", "hypotheses.jsonl"),
            "state_dir": state_dir,
            "log_path": LOG_PATH,
            "interval_seconds": 60,
            "exchange_id": "bybit",
            "dry_run": True,                # paper trading only
        }
    except (AttributeError):
        # ESC / pregunta cancelada -> volver al menú.
        # KeyboardInterrupt NO se captura: Ctrl+C = cierre total del sistema.
        return None


def burst_wizard() -> Optional[Dict]:
    """Interactive burst-scalping configuration wizard."""
    console.print(Panel(
        "[bold cyan]Wizard Burst Scalping[/bold cyan]\n"
        "Ráfagas tendenciales: $10 margen × leverage, TP 0.4-0.8%.\n"
        "Modo paper trading. Los datos son SIEMPRE reales (Bybit).",
        expand=False))
    try:
        # Symbol selection: interactive Top-20 or manual
        use_top = questionary.select(
            "Selección de símbolos:",
            choices=[
                questionary.Choice("Top-20 por volumen (recomendado)",
                                   value="top20"),
                questionary.Choice("Ingresar manualmente", value="manual"),
            ]).unsafe_ask()
        if use_top is None:
            return None

        if use_top == "top20":
            console.print("[cyan]Obteniendo Top-20 por volumen...[/cyan]")
            top_assets = fetch_top_volume_assets("bybit", 20)
            try:
                _cb_result = questionary.checkbox(
                    "Selecciona símbolos (espacio marcar, Enter confirmar):",
                    choices=[questionary.Choice(s, value=s) for s in top_assets]
                ).unsafe_ask()
            except (AttributeError, TypeError):
                return None
            # questionary may return list or tuple depending on version
            if isinstance(_cb_result, tuple):
                selected = list(_cb_result[0]) if _cb_result and _cb_result[0] else []
            elif isinstance(_cb_result, list):
                selected = _cb_result
            else:
                selected = list(_cb_result) if _cb_result else []
            if not selected:
                console.print("[red]Debes seleccionar al menos un símbolo[/red]")
                return None
            symbols = selected
        else:
            raw = questionary.text(
                "Símbolos (separados por coma):",
                default="BTC/USDT").unsafe_ask()
            if raw is None:
                return None
            symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
            if not symbols:
                console.print("[red]Se requiere al menos un símbolo[/red]")
                return None

        margin = ask_float("Margen por entrada (USD, min 5)", "10", lo=5)
        if margin is None:
            return None
        leverage = ask_int("Leverage (1-20)", "10", lo=1)
        if leverage is None:
            return None
        leverage = max(1, min(20, leverage))

        timeframe = questionary.select(
            "Timeframe:", choices=["1m", "5m", "15m", "1h"],
            default="5m").unsafe_ask()
        if timeframe is None:
            return None

        tp_pct = ask_float("Take-profit % (0.4-0.8 recommended)", "0.006")
        if tp_pct is None:
            return None
        tp_pct = max(0.004, min(0.008, tp_pct))

        lookback_days = ask_int("Lookback days (backtest)", "14", lo=1)
        if lookback_days is None:
            return None
        hyp_per_cycle = ask_int("Hipótesis nuevas por ciclo", "5", lo=1)
        if hyp_per_cycle is None:
            return None

        state_dir = os.path.join(PROJECT_ROOT, "runtime", "state_burst")
        os.makedirs(state_dir, exist_ok=True)

        return {
            "symbols": symbols,
            "timeframe": timeframe,
            "lookback_days": lookback_days,
            "initial_capital": 1000.0,
            "entry_pct": 0.1,               # ignored in burst mode (margin-based)
            "take_profit_pct": tp_pct,
            "min_paper_trades": 3,
            "hypotheses_per_cycle": hyp_per_cycle,
            "kb_path": os.path.join(PROJECT_ROOT, "runtime", "hypotheses_burst.jsonl"),
            "state_dir": state_dir,
            "log_path": BURST_LOG_PATH,
            "interval_seconds": 15,
            "exchange_id": "bybit",
            "dry_run": True,
            "mode": "burst",
            "burst_margin": margin,
            "burst_leverage": leverage,
        }
    except (AttributeError):
        return None


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

_price_cache: Dict[str, tuple] = {}


def _get_current_price(symbol: str, exchange_id: str) -> Optional[float]:
    """Throttled real price lookup (20s cache per symbol)."""
    cached = _price_cache.get(symbol)
    now = time.time()
    if cached and now - cached[1] < 20:
        return cached[0]
    try:
        import ccxt
        ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
        ticker = ex.fetch_ticker(symbol)
        price = ticker.get("last") or ticker.get("close")
        _price_cache[symbol] = (price, now)
        return price
    except Exception:
        return cached[0] if cached else None


def fetch_top_volume_assets(exchange_id: str = "bybit", n: int = 20) -> list:
    """Top-N USDT pairs by quoteVolume, stablecoin bases excluded."""
    STABLES = {"USDC", "BUSD", "DAI", "TUSD", "USDP", "FDUSD",
               "USDJ", "GBP", "EUR", "AUD", "BRL", "JPY"}
    try:
        import ccxt
        ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
        tickers = ex.fetch_tickers()
    except Exception:
        return ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT"]
    pairs = []
    for sym, t in tickers.items():
        # Bybit returns "BTC/USDT:USDT" — normalize to "BTC/USDT"
        clean = sym.split(":")[0] if ":" in sym else sym
        if not clean.endswith("/USDT"):
            continue
        base = clean.split("/")[0]
        if base in STABLES:
            continue
        qv = float(t.get("quoteVolume") or 0)
        if qv > 0:
            pairs.append((clean, qv))
    pairs.sort(key=lambda x: x[1], reverse=True)
    seen = set()
    result = []
    for s, _ in pairs:
        if s not in seen:
            seen.add(s)
            result.append(s)
        if len(result) >= n:
            break
    return result if result else [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT"]


def _read_paper_trades(state_dir: str):
    path = os.path.join(state_dir, "paper_executions.jsonl")
    trades = []
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        trades.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return trades


def _count_open_positions(state_dir: str) -> int:
    path = os.path.join(state_dir, "positions.jsonl")
    if not os.path.exists(path):
        return 0
    return sum(1 for line in open(path, encoding="utf-8") if line.strip())



# --- O5: analitica de aprendizaje para el Monitor -------------------------
SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(values) -> str:
    if not values:
        return "-"
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    return "".join(SPARK[min(7, int((v - lo) / rng * 7))] for v in values)


def _learning_panel_data(state_dir: str, trades, stats: Dict) -> Dict:
    """Curva PnL de ultimos cierres, estado/progreso de graduacion y
    trayectoria del libro (O5)."""
    closures = [float(t.get("pnl", 0.0)) for t in trades
                if "motivo_cierre" in t][-30:]
    cum = []
    acc = 0.0
    for p in closures:
        acc += p
        cum.append(acc)
    grad_path = os.path.join(state_dir, "graduation.json")
    grad = None
    if os.path.exists(grad_path):
        try:
            with open(grad_path) as fh:
                grad = json.load(fh)
        except (OSError, json.JSONDecodeError):
            grad = None
    win = 30
    tail = closures[-win:]
    mean_w = sum(tail) / len(tail) if tail else 0.0
    ic90_lb = 0.0
    if len(tail) >= 8:
        import statistics as _st
        ic90_lb = mean_w - 1.2816 * (_st.pstdev(tail) / len(tail) ** 0.5)
    last10 = [float(t.get("pnl_pct") or 0.0)
              for t in trades if "motivo_cierre" in t]
    recent = sum(last10[-10:]) / max(1, len(last10[-10:]))
    prior = sum(last10[-20:-10]) / max(1, len(last10[-20:-10]) - (
        0 if len(last10) >= 20 else max(0, 10 - len(last10))))         if len(last10) > 10 else 0.0
    return {
        "curve": _sparkline(cum),
        "graduated": bool(grad and grad.get("graduated")),
        "grad_at": time.strftime(
            "%d %b %H:%M", time.localtime(grad["at"])) if grad else "-",
        "grad_mean": grad.get("mean_pnl_pct", 0.0) if grad else 0.0,
        "window_n": len(tail),
        "window_size": win,
        "window_mean": mean_w,
        "ic90_lb": ic90_lb,
        "recent10": recent,
        "prior10": prior,
        "novelty_last": stats.get("novelty_rate_last_cycle"),
        "novelty_avg": stats.get("novelty_cum_avg"),
    }


def render_monitor(runtime: RuntimeState):
    stats = runtime.stats
    cfg = stats.get("config", {})
    state_dir = cfg.get("state_dir", "runtime/state")
    state = "RUNNING" if runtime.running else "STOPPED"

    header = Table.grid(padding=(0, 2))
    header.add_column(justify="left")
    header.add_row(Text("QUANT-MATH MONITOR", style="bold cyan"))
    status = Text(f"● {state}", style="bold green" if state == "RUNNING" else "bold red")
    cycles = stats.get("cycles_completed", 0)
    generated = stats.get("hypotheses_generated", 0)
    evaluated = stats.get("hypotheses_evaluated", 0)

    open_pos = _count_open_positions(state_dir)

    # Libro permanente: cierres realizados (motivo_cierre) + MtM solo de
    # entradas que siguen vivas (sin closure posterior para su key).
    # Operaciones PRE-integracion (entry < cutoff en learning_meta.json)
    # se excluyen del MtM y del PnL nuevo: son historial, no exposicion.
    from quant_math.ml.feature_store import integration_cutoff
    cutoff = integration_cutoff(state_dir)
    trades = _read_paper_trades(state_dir) if runtime.config_dict else []
    closed_keys = set()
    total_closed = wins = losses = 0
    realized = realized_legacy = 0.0
    open_entries = []
    for rec in trades:
        key = rec.get("key")
        if "motivo_cierre" in rec:
            total_closed += 1
            pnl = float(rec.get("pnl", 0.0))
            is_legacy = cutoff and float(rec.get("exit_time") or 0) < cutoff
            if is_legacy:
                realized_legacy += pnl
            else:
                realized += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            if key:
                closed_keys.add(key)
        elif cutoff and float(rec.get("timestamp") or 0) < cutoff:
            continue                      # fantasma pre-integracion: no expone
        else:
            open_entries.append(rec)
    unrealized = 0.0
    for t in open_entries:
        cur = _get_current_price(t["symbol"], cfg.get("exchange_id", "bybit"))
        ref = cur if cur is not None else t["entry_price"]
        direction = 1 if t["side"] == "buy" else -1
        unrealized += t["quantity"] * (ref - t["entry_price"]) * direction

    equity = cfg.get("initial_capital", 0.0) + realized + unrealized

    body = Table(show_header=True, header_style="bold magenta", expand=True)
    body.add_column("Métrica")
    body.add_column("Valor", justify="right")
    body.add_row("Estado", status)
    body.add_row("Ciclos completados", str(cycles))
    body.add_row("Hipótesis generadas", str(generated))
    body.add_row("Hipótesis evaluadas", str(evaluated))
    body.add_row("Operaciones abiertas", str(open_pos))
    body.add_row("Operaciones cerradas", str(total_closed))
    body.add_row("Positivas", f"[green]{wins}[/green]")
    body.add_row("Negativas", f"[red]{losses}[/red]")
    pnl_style = "green" if unrealized >= 0 else "red"
    body.add_row("Beneficio/Pérdida (MtM)", Text(f"{unrealized:+,.2f} USD", style=pnl_style))
    real_style = "green" if realized >= 0 else "red"
    body.add_row("PnL realizado (cierres)", Text(f"{realized:+,.2f} USD", style=real_style))
    if abs(realized_legacy) > 0.005:
        body.add_row("PnL legacy (pre-integración)",
                     Text(f"{realized_legacy:+,.2f} USD", style="dim"))
    body.add_row("Equity", f"${equity:,.2f}")
    body.add_row("Último ciclo",
                 time.strftime("%H:%M:%S", time.localtime(stats.get("last_cycle_at", 0)))
                 if stats.get("last_cycle_at") else "-")

    # O5: panel de aprendizaje
    L = _learning_panel_data(state_dir, trades, stats)
    trend = ("→" if abs(L["recent10"] - L["prior10"]) < 0.05
             else ("▲" if L["recent10"] > L["prior10"] else "▼"))
    tstyle = "green" if L["recent10"] >= L["prior10"] else "red"
    if L["graduated"]:
        grad_txt = Text(f"GRADUADO {L['grad_at']} "
                        f"(media ventana {L['grad_mean']:+.3f}%)",
                        style="bold green")
    else:
        grad_txt = (f"aprendiendo {L['window_n']}/{L['window_size']} · "
                    f"media {L['window_mean']:+.3f}% · IC90_lb "
                    f"{L['ic90_lb']:+.3f}%")
    nov = ("-"
           if L["novelty_last"] is None
           else f"{L['novelty_last'] * 100:.0f}% "
                f"(prom {L['novelty_avg'] * 100:.0f}%)")
    pnl_style2 = "green" if L["recent10"] >= 0 else "red"
    body.add_row("Graduación (PB/O1)", grad_txt)
    body.add_row("Curva PnL (últimos 30)", Text(L["curve"]))
    body.add_row("Trayectoria libro (últ10 vs prev10)",
                 Text(f"{L['recent10']:+.3f}% vs {L['prior10']:+.3f}% {trend}",
                      style=tstyle))
    body.add_row("PnL medio últimos 10",
                 Text(f"{L['recent10']:+.3f}%", style=pnl_style2))
    body.add_row("Novedad generativa (O4)", nov)

    # V2 B5: burst-specific panel
    if stats.get("mode") == "burst":
        b = stats.get("burst_stats", {})
        body.add_row("── BURST SCALPING ──", "")
        body.add_row("Entries burst (ciclo/total)",
                     f"{b.get('entries_this_cycle', 0)} / "
                     f"{b.get('total_entries', 0)}")
        body.add_row("Cierres burst",
                     f"{b.get('total_closures', 0)} "
                     f"(W:{b.get('wins', 0)} L:{b.get('losses', 0)})")
        wr = b.get('win_rate', 0)
        body.add_row("Win rate burst",
                     Text(f"{wr:.0f}%",
                          style="green" if wr >= 50 else "red"))
        cd = b.get('cooldown_remaining', 0)
        body.add_row("Cooldown restante",
                     Text(f"{cd} ciclos",
                          style="yellow" if cd > 0 else "dim"))
        cl = b.get('consecutive_losses', 0)
        if cl > 0:
            body.add_row("Pérdidas consecutivas",
                         Text(str(cl), style="red"))

    config_panel = Table.grid(padding=(0, 1))
    for key in ("symbols", "timeframe", "initial_capital", "entry_pct",
                "take_profit_pct", "stop_loss_pct", "lookback_days",
                "min_paper_trades", "hypotheses_per_cycle", "exchange_id",
                "mode"):
        if key in cfg:
            config_panel.add_row(key, str(cfg[key]))

    outer = Table.grid()
    outer.add_row(header)
    outer.add_row(body)
    outer.add_row(Panel(config_panel, title="Config activa"))

    return Panel(
        outer,
        title="Monitor en vivo (ESC para volver)",
        border_style="cyan" if state == "RUNNING" else "red",
    )


def monitor_loop(runtime: RuntimeState):
    """Live monitor; ESC returns to menu without stopping anything."""
    console.print("[dim]Monitor en vivo — presiona ESC para volver al menú[/dim]")
    try:
        with Live(render_monitor(runtime), console=console, refresh_per_second=2,
                  screen=False, redirect_stdout=False, redirect_stderr=False) as live:
            while True:
                live.update(render_monitor(runtime))
                import select
                import termios
                import tty
                fd = sys.stdin.fileno()
                old_attrs = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    r, _, _ = select.select([sys.stdin], [], [], 1.0)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch == "\x1b":
                            return
                        if ch == "\x03":
                            raise KeyboardInterrupt
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        console.print(f"[yellow]Monitor cerrado: {exc}[/yellow]")


# ---------------------------------------------------------------------------
# Log viewer
# ---------------------------------------------------------------------------

def view_log():
    view_log_path(LOG_PATH)


def view_log_path(log_path: str):
    title = os.path.basename(log_path)
    if not os.path.exists(log_path):
        console.print(f"[yellow]Sin logs todavía ({title} no existe)[/yellow]")
        return questionary.press_any_key_to_continue().unsafe_ask()
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    page_size = 40
    total_pages = max(1, (len(lines) + page_size - 1) // page_size)
    page = max(0, total_pages - 1)  # start at the end (most recent)
    while True:
        chunk = lines[page * page_size:(page + 1) * page_size]
        text = "".join(chunk) or "(vacía)"
        console.print(Panel(text, title=f"{title} — página {page + 1}/{total_pages}"))
        try:
            choice = questionary.select(
                "Log:  (↑/↓ + Enter)",
                choices=[
                    questionary.Choice("Siguiente página →", value="next"),
                    questionary.Choice("← Página anterior", value="prev"),
                    questionary.Choice("Volver al menú (ESC)", value="back"),
                ],
            ).unsafe_ask()
        except (AttributeError):
            return
        if choice in (None, "back"):
            return
        if choice == "next" and page < total_pages - 1:
            page += 1
        elif choice == "prev" and page > 0:
            page -= 1


# ---------------------------------------------------------------------------
# Historial de operaciones (libro permanente)
# ---------------------------------------------------------------------------

def _read_closures(state_dir: str):
    path = os.path.join(state_dir, "paper_executions.jsonl")
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "motivo_cierre" in rec:
                out.append(rec)
    return out


def view_history(runtime: RuntimeState):
    from quant_math.ml.feature_store import integration_cutoff
    state_dir = (runtime.config_dict or {}).get(
        "state_dir", os.path.join(PROJECT_ROOT, "runtime", "state"))
    cutoff = integration_cutoff(state_dir)
    closures = _read_closures(state_dir)
    if not closures:
        console.print("[yellow]Sin operaciones cerradas todavia "
                      "(libro permanente vacio)[/yellow]")
        try:
            questionary.press_any_key_to_continue().unsafe_ask()
        except AttributeError:
            pass
        return

    def fmt_ts(ts):
        return time.strftime("%m-%d %H:%M", time.localtime(ts)) if ts else "-"

    page_size = 12
    total_pages = max(1, (len(closures) + page_size - 1) // page_size)
    page = 0
    while True:
        chunk = closures[page * page_size:(page + 1) * page_size]
        table = Table(show_header=True, header_style="bold magenta",
                     expand=True)
        for col in ("Entrada", "Cierre", "Simbolo", "Hipotesis", "Side",
                    "P.entrada", "P.salida", "PnL USD", "PnL %", "Motivo"):
            table.add_column(col)
        for c in chunk:
            pnl = float(c.get("pnl", 0.0))
            style = "green" if pnl > 0 else "red"
            table.add_row(
                fmt_ts(c.get("entry_time")), fmt_ts(c.get("exit_time")),
                c.get("symbol", ""), str(c.get("hypothesis_id", ""))[:14],
                (c.get("side") or "").upper(),
                f"{c.get('entry_price', 0):g}", f"{c.get('exit_price', 0):g}",
                Text(f"{pnl:+.2f}", style=style),
                Text(f"{c.get('pnl_pct', 0):+.2f}%", style=style),
                str(c.get("motivo_cierre", ""))
                + ("·legacy" if cutoff and
                   float(c.get("exit_time") or 0) < cutoff else ""))
        pnls = [float(c.get("pnl", 0.0)) for c in closures]
        wins = sum(1 for p in pnls if p > 0)
        summary = Table.grid(padding=(0, 2))
        summary.add_column(justify="right")
        summary.add_column()
        summary.add_row("Operaciones cerradas:", str(len(closures)))
        summary.add_row("Positivas / Negativas:",
                        f"[green]{wins}[/green] / [red]{len(pnls)-wins}[/red]")
        summary.add_row("PnL total:",
                        Text(f"{sum(pnls):+,.2f} USD",
                             style="green" if sum(pnls) >= 0 else "red"))
        if cutoff:
            legacy = [c for c in closures
                      if float(c.get("exit_time") or 0) < cutoff]
            if legacy:
                lp = sum(float(c.get("pnl", 0)) for c in legacy)
                summary.add_row(
                    f"Legacy pre-integración ({len(legacy)} ops):",
                    Text(f"{lp:+,.2f} USD", style="dim"))
        console.print(Panel(table, title=f"Historial — pagina "
                          f"{page+1}/{total_pages}"))
        console.print(Panel(summary, title="Resumen"))

        try:
            choice = questionary.select(
                "Historial:",
                choices=[
                    questionary.Choice("Siguiente pagina →", value="next"),
                    questionary.Choice("← Pagina anterior", value="prev"),
                    questionary.Choice("Volver al menu (ESC)", value="back"),
                ]).unsafe_ask()
        except (AttributeError, KeyboardInterrupt):
            return
        if choice in (None, "back"):
            return
        if choice == "next" and page < total_pages - 1:
            page += 1
        elif choice == "prev" and page > 0:
            page -= 1


# ---------------------------------------------------------------------------
# Historial Burst (libro permanente de burst)
# ---------------------------------------------------------------------------

def view_burst_history():
    state_dir = BURST_STATE_DIR
    closures = _read_closures(state_dir)
    if not closures:
        console.print("[yellow]Sin operaciones burst cerradas todavia "
                      "(libro burst vacio)[/yellow]")
        try:
            questionary.press_any_key_to_continue().unsafe_ask()
        except AttributeError:
            pass
        return

    def fmt_ts(ts):
        return time.strftime("%m-%d %H:%M", time.localtime(ts)) if ts else "-"

    page_size = 12
    total_pages = max(1, (len(closures) + page_size - 1) // page_size)
    page = 0
    while True:
        chunk = closures[page * page_size:(page + 1) * page_size]
        table = Table(show_header=True, header_style="bold magenta",
                      expand=True)
        for col in ("Entrada", "Cierre", "Simbolo", "Side",
                    "P.entrada", "P.salida", "PnL USD", "PnL %",
                    "Margin", "Lev", "Motivo"):
            table.add_column(col)
        for c in chunk:
            pnl = float(c.get("pnl", 0.0))
            style = "green" if pnl > 0 else "red"
            margin = c.get("margin_usd", c.get("margin", ""))
            lev = c.get("leverage", "")
            table.add_row(
                fmt_ts(c.get("entry_time")), fmt_ts(c.get("exit_time")),
                c.get("symbol", ""),
                (c.get("side") or "").upper(),
                f"{c.get('entry_price', 0):g}", f"{c.get('exit_price', 0):g}",
                Text(f"{pnl:+.2f}", style=style),
                Text(f"{c.get('pnl_pct', 0):+.2f}%", style=style),
                f"${margin}" if margin else "-",
                f"{lev}×" if lev else "-",
                str(c.get("motivo_cierre", "")))
        pnls = [float(c.get("pnl", 0.0)) for c in closures]
        wins = sum(1 for p in pnls if p > 0)
        summary = Table.grid(padding=(0, 2))
        summary.add_column(justify="right")
        summary.add_column()
        summary.add_row("Operaciones burst cerradas:", str(len(closures)))
        summary.add_row("Positivas / Negativas:",
                        f"[green]{wins}[/green] / [red]{len(pnls)-wins}[/red]")
        summary.add_row("PnL total burst:",
                        Text(f"{sum(pnls):+,.2f} USD",
                             style="green" if sum(pnls) >= 0 else "red"))
        console.print(Panel(table, title=f"Historial Burst — pagina "
                          f"{page+1}/{total_pages}"))
        console.print(Panel(summary, title="Resumen Burst"))

        try:
            choice = questionary.select(
                "Historial Burst:",
                choices=[
                    questionary.Choice("Siguiente página →", value="next"),
                    questionary.Choice("← Página anterior", value="prev"),
                    questionary.Choice("Volver al menú (ESC)", value="back"),
                ],
            ).unsafe_ask()
        except (AttributeError, KeyboardInterrupt):
            return
        if choice in (None, "back"):
            return
        if choice == "next" and page < total_pages - 1:
            page += 1
        elif choice == "prev" and page > 0:
            page -= 1


# ---------------------------------------------------------------------------
# Burst Monitor (panel dedicado para burst scalping)
# ---------------------------------------------------------------------------

def _burst_read_paper_trades():
    return _read_paper_trades(BURST_STATE_DIR)


def _burst_count_open_positions():
    return _count_open_positions(BURST_STATE_DIR)


def render_burst_monitor(runtime: RuntimeState):
    stats = runtime.stats
    cfg = stats.get("config", {})
    state_dir = cfg.get("state_dir", BURST_STATE_DIR)
    state = "RUNNING" if runtime.running else "STOPPED"

    header = Table.grid(padding=(0, 2))
    header.add_column(justify="left")
    header.add_row(Text("BURST SCALPING MONITOR", style="bold cyan"))
    status = Text(f"● {state}", style="bold green" if state == "RUNNING" else "bold red")
    cycles = stats.get("cycles_completed", 0)
    generated = stats.get("hypotheses_generated", 0)

    open_pos = _burst_count_open_positions()
    trades = _burst_read_paper_trades()
    closed_keys = set()
    total_closed = wins = losses = 0
    total_pnl = 0.0
    open_entries = []
    for t in trades:
        key = t.get("key")
        if "motivo_cierre" in t:
            if key:
                closed_keys.add(key)
            total_closed += 1
            pnl = float(t.get("pnl", 0.0))
            total_pnl += pnl
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
        elif key and key not in closed_keys:
            open_entries.append(t)
    win_rate = (wins / total_closed * 100) if total_closed else 0.0

    # MtM: fetch current prices for open entries
    unrealized = 0.0
    for t in open_entries:
        cur = _get_current_price(t["symbol"], cfg.get("exchange_id", "bybit"))
        ref = cur if cur is not None else t["entry_price"]
        direction = 1 if t["side"] == "buy" else -1
        qty = float(t.get("quantity", 0))
        unrealized += qty * (ref - float(t["entry_price"])) * direction

    # Burst-specific stats
    b = stats.get("burst_stats", {})
    entries_this_cycle = b.get("entries_this_cycle", 0)
    total_entries = b.get("total_entries", 0)
    total_closures_burst = b.get("total_closures", 0)
    wins_burst = b.get("wins", 0)
    losses_burst = b.get("losses", 0)
    win_rate_burst = b.get("win_rate", 0.0)
    cooldown_remaining = b.get("cooldown_remaining", 0)
    consecutive_losses = b.get("consecutive_losses", 0)

    # Exposure
    margin_locked = sum(float(t.get("margin_usd", t.get("margin", 0)) or 0)
                        for t in trades
                        if "motivo_cierre" not in t and t.get("key") not in closed_keys)
    notional_exposed = sum(
        float(t.get("margin_usd", t.get("margin", 0)) or 0) *
        float(t.get("leverage", 1) or 1)
        for t in trades
        if "motivo_cierre" not in t and t.get("key") not in closed_keys)

    body = Table.grid(padding=(0, 1))
    body.add_column(style="bold")
    body.add_column()
    body.add_row("Status", status)
    body.add_row("Ciclos completados", str(cycles))
    body.add_row("Hipótesis generadas", str(generated))
    body.add_row("Posiciones abiertas", str(open_pos))
    body.add_row("Exposición margin",
                 Text(f"${margin_locked:,.2f}", style="yellow"))
    body.add_row("Exposición notional",
                 Text(f"${notional_exposed:,.2f}", style="dim"))

    # --- PnL ---
    pnl_style = "green" if total_pnl >= 0 else "red"
    body.add_row("PnL total (cerradas)",
                 Text(f"${total_pnl:+,.2f}", style=pnl_style))
    body.add_row("PnL MtM (abiertas)",
                 Text(f"${unrealized:+,.2f}",
                      style="green" if unrealized >= 0 else "red"))
    body.add_row("Operaciones cerradas", str(total_closed))
    body.add_row("Win/Loss (global)",
                 f"[green]{wins}[/green] / [red]{losses}[/red]")
    body.add_row("Win rate (global)",
                 Text(f"{win_rate:.0f}%", style="green" if win_rate >= 50 else "red"))

    # --- Burst metrics ---
    body.add_row("── BURST ──", "")
    body.add_row("Entries (ciclo/total)",
                 f"{entries_this_cycle} / {total_entries}")
    body.add_row("Cierres burst",
                 f"{total_closures_burst} "
                 f"(W:{wins_burst} L:{losses_burst})")
    body.add_row("Win rate burst",
                 Text(f"{win_rate_burst:.0f}%",
                      style="green" if win_rate_burst >= 50 else "red"))
    cd_style = "yellow" if cooldown_remaining > 0 else "dim"
    body.add_row("Cooldown restante",
                 Text(f"{cooldown_remaining} ciclos", style=cd_style))
    if consecutive_losses > 0:
        body.add_row("Pérdidas consecutivas",
                     Text(str(consecutive_losses), style="red"))

    # --- Hypothesis trajectory ---
    kb_path = cfg.get("kb_path", os.path.join(PROJECT_ROOT, "runtime",
                                                "hypotheses_burst.jsonl"))
    if os.path.exists(kb_path):
        try:
            with open(kb_path) as f:
                lines_k = f.readlines()
        except OSError:
            lines_k = []
        total_hyp = len(lines_k)
        if total_hyp > 0:
            pcts = []
            for ln in lines_k[-20:]:
                try:
                    d = json.loads(ln)
                    pcts.append(float(d.get("pnl_pct", 0.0)))
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
            if pcts:
                prom = sum(pcts) / len(pcts)
                style_p = "green" if prom > 0 else "red"
                body.add_row("PnL prom. últimas hip.",
                             Text(f"{prom:+.2f}%", style=style_p))
            body.add_row("Total hipótesis en KB", str(total_hyp))

    # --- Graduation attempt ---
    grad_path = os.path.join(state_dir, "graduation.json")
    if os.path.exists(grad_path):
        try:
            with open(grad_path) as f:
                grad = json.load(f)
        except (json.JSONDecodeError, OSError):
            grad = None
        if grad:
            g_at = grad.get("at")
            body.add_row("Graduación PB",
                         time.strftime("%d-%m-%Y %H:%M",
                                       time.localtime(g_at)) if g_at else "-")

    config_panel = Table.grid(padding=(0, 1))
    for key in ("symbols", "timeframe", "initial_capital",
                "take_profit_pct", "stop_loss_pct", "lookback_days",
                "min_paper_trades", "hypotheses_per_cycle", "exchange_id",
                "mode", "burst_margin", "burst_leverage"):
        if key in cfg:
            config_panel.add_row(key, str(cfg[key]))

    outer = Table.grid()
    outer.add_row(header)
    outer.add_row(body)
    outer.add_row(Panel(config_panel, title="Config Burst"))

    return Panel(
        outer,
        title="[bold]BURST SCALPING — Monitor[/bold]",
        border_style="cyan",
    )


def burst_monitor_loop(runtime: RuntimeState):
    """Live burst monitor; ESC returns to menu without stopping anything."""
    console.print("[dim]Burst monitor — presiona ESC para volver al menú[/dim]")
    try:
        with Live(render_burst_monitor(runtime), console=console,
                  refresh_per_second=1, screen=False,
                  redirect_stdout=False, redirect_stderr=False) as live:
            while True:
                live.update(render_burst_monitor(runtime))
                import select
                import termios
                import tty
                fd = sys.stdin.fileno()
                old_attrs = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    r, _, _ = select.select([sys.stdin], [], [], 1.0)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch == "\x1b":
                            return
                        if ch == "\x03":
                            raise KeyboardInterrupt
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        console.print(f"[red]Error en burst monitor: {exc}[/red]")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def shutdown(runtime: RuntimeState):
    if runtime.running:
        console.print("[yellow]Deteniendo orchestrator...[/yellow]")
        runtime.stop()
        console.print("[green]Orchestrator detenido.[/green]")

    stop_vm_env = os.environ.get("QUANTMATH_VM_STOP_ON_EXIT")
    if runtime._pg_alive():
        resp = False
        if stop_vm_env == "1":
            resp = True
        elif stop_vm_env == "0" or not sys.stdin.isatty():
            resp = False
        else:
            try:
                resp = bool(questionary.confirm(
                    "¿Detener también la VM PostgreSQL?",
                    default=False).unsafe_ask())
            except Exception:
                resp = False            # ESC o Ctrl+C -> salir sin tocar VM
        if resp:
            console.print("[cyan]Deteniendo VM PostgreSQL...[/cyan]")
            ok = runtime._stop_pg_vm()
            if ok:
                console.print("[green]VM PostgreSQL detenida.[/green]")
            else:
                console.print("[yellow]No se pudo confirmar el apagado de "
                              "la VM (ver autostart.log)[/yellow]")
        else:
            console.print("[dim]La VM PostgreSQL sigue corriendo en "
                          "segundo plano.[/dim]")
    console.print("[bold]Hasta luego.[/bold]")


def main():
    runtime = RuntimeState()
    try:
        while True:
            try:
                is_burst = (runtime.config_dict or {}).get("mode") == "burst"
                action = questionary.select(
                    "QUANT-MATH — Menú principal  (↑/↓ + Enter)",
                    choices=[
                        questionary.Choice("Iniciar Quant-Math",
                                           value="start",
                                           disabled="ya está corriendo" if runtime.running else None),
                        questionary.Choice("Detener investigación",
                                           value="stop",
                                           disabled="no está corriendo" if not runtime.running else None),
                        questionary.Choice("Monitor", value="monitor"),
                        questionary.Choice("Ver log", value="log"),
                        questionary.Choice("Historial de operaciones",
                                           value="history"),
                        questionary.Choice("Iniciar Burst Scalping",
                                           value="start_burst",
                                           disabled="ya está corriendo" if runtime.running else None),
                        questionary.Choice("Historial Burst",
                                           value="burst_history",
                                           disabled=None if is_burst else "solo disponible con Burst activo"),
                        questionary.Choice("Ver log Burst",
                                           value="burst_log",
                                           disabled=None if is_burst else "solo disponible con Burst activo"),
                        questionary.Choice("Salir", value="quit"),
                    ],
                ).unsafe_ask()
            except KeyboardInterrupt:
                # Ctrl+C en el menú principal -> cierre total
                print()
                shutdown(runtime)
                return 0

            if action is None:  # ESC on main menu
                if runtime.running:
                    console.print("[dim]ESC: sigue corriendo en fondo. "
                                  "Usa 'Salir' o 'Detener investigación' para cerrar.[/dim]")
                continue

            # Ctrl+C en cualquier sub-pantalla propaga -> cierre total (outer)
            _dispatch(runtime, action)
    except KeyboardInterrupt:
        print()
        shutdown(runtime)
        return 0
    return 0


def _dispatch(runtime: RuntimeState, action: str):
    if action == "start":
        cfg = wizard()
        if cfg is None:
            console.print("[dim]Wizard cancelado.[/dim]")
            return
        runtime.start(cfg)
        console.print(f"[green]Orchestrator iniciado en proceso de fondo "
                      f"(pid={runtime.process.pid}). Logs: {LOG_PATH}[/green]")
        try:
            questionary.press_any_key_to_continue(message="(ENTER/tecla para volver)").unsafe_ask()
        except (AttributeError):
            pass

    elif action == "stop":
        if runtime.stop():
            console.print("[green]Investigación detenida.[/green]")
        else:
            console.print("[yellow]No hay proceso activo.[/yellow]")

    elif action == "start_burst":
        cfg = burst_wizard()
        if cfg is None:
            console.print("[dim]Wizard burst cancelado.[/dim]")
            return
        runtime.start(cfg)
        console.print(f"[green]Burst Scalping iniciado (pid={runtime.process.pid}). "
                      f"Logs: {BURST_LOG_PATH}[/green]")
        try:
            questionary.press_any_key_to_continue(message="(ENTER/tecla para volver)").unsafe_ask()
        except (AttributeError):
            pass

    elif action == "monitor":
        is_burst = (runtime.config_dict or {}).get("mode") == "burst"
        if is_burst:
            burst_monitor_loop(runtime)
        else:
            monitor_mode = questionary.select(
                "¿Qué monitor?",
                choices=[
                    questionary.Choice("Quant-Math", value="classic"),
                    questionary.Choice("Burst Scalping", value="burst"),
                ]).unsafe_ask()
            if monitor_mode == "burst":
                burst_monitor_loop(runtime)
            else:
                monitor_loop(runtime)

    elif action == "log":
        is_burst = (runtime.config_dict or {}).get("mode") == "burst"
        if is_burst:
            view_log_path(BURST_LOG_PATH)
        else:
            view_log()

    elif action == "history":
        view_history(runtime)

    elif action == "burst_history":
        view_burst_history()

    elif action == "burst_log":
        view_log_path(BURST_LOG_PATH)

    elif action == "quit":
        shutdown(runtime)
        raise SystemExit(0)


if __name__ == "__main__":
    sys.exit(main())
