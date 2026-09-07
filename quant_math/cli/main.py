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
from typing import Dict, List, Optional

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
    # Lower process priority for battery savings on Android
    try:
        os.nice(10)
    except (OSError, AttributeError):
        pass

    # Termux wakelock: acquire to keep CPU alive during cycles
    _is_termux = os.path.exists("/data/data/com.termux")
    def _acquire_wakelock():
        if _is_termux:
            try:
                subprocess.run(["termux-wake-lock"], timeout=2, capture_output=True)
            except Exception:
                pass
    def _release_wakelock():
        if _is_termux:
            try:
                subprocess.run(["termux-wake-unlock"], timeout=2, capture_output=True)
            except Exception:
                pass

    log_path = cfg_dict.get("log_path", LOG_PATH)
    # Route ALL stdout/stderr to the log file before importing heavy modules
    class _CappedStream:
        """stdout del hijo con techo de tamano: rota a .1 al superar max_mb."""

        def __init__(self, path, max_mb=150):
            self.path = path
            self.max_bytes = int(max_mb * 1024 * 1024)
            self.fh = open(path, "a", buffering=8192)

        def write(self, data):
            try:
                if self.fh.tell() > self.max_bytes:
                    self.fh.close()
                    bak = self.path + ".1"
                    if os.path.exists(bak):
                        os.remove(bak)
                    os.replace(self.path, bak)
                    self.fh = open(self.path, "a", buffering=8192)
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
    _acquire_wakelock()
    try:
        orch.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        orch.mark_stopped()
        _release_wakelock()
        cap.fh.close()


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


class _DetachedProcess:
    """Wrapper for a subprocess.Popen that provides mp.Process-like interface."""

    def __init__(self, pid: int, mode: str):
        self.pid = pid
        self.mode = mode
        self._proc: Optional[subprocess.Popen] = None

    def is_alive(self) -> bool:
        """Check if the process is still running via PID file + os.kill."""
        try:
            os.kill(self.pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    @property
    def exitcode(self) -> Optional[int]:
        return None  # detached processes — exitcode not tracked


class RuntimeState:
    """Tracks background orchestrator sessions (one process per session).

    Sessions are named (e.g. "classic", "burst", "classic-ETH",
    "burst-EURUSD"), each with isolated state_dir/KB/log. Legacy names
    "classic"/"burst" keep their historic paths.
    """

    def __init__(self):
        self.processes: Dict[str, mp.Process] = {}
        self.configs: Dict[str, Dict] = {}
        self._minimized = False  # True after minimize — exit won't kill processes

    @staticmethod
    def _pg_alive(timeout=1.5) -> bool:
        """PostgreSQL eliminado — siempre retorna False."""
        return False

    def _ensure_pg_vm(self):
        """PostgreSQL VM eliminado — KB opera en modo JSONL puro."""
        console.print("[dim]KB: modo JSONL (PostgreSQL eliminado)[/dim]")

    def _stop_pg_vm(self, timeout: float = 25.0) -> bool:
        """PostgreSQL VM eliminado — no hay nada que detener."""
        return True

    # --- Process management (multi-session) ---

    @staticmethod
    def _default_state_dir(session: str) -> str:
        if session == "classic":
            return os.path.join(PROJECT_ROOT, "runtime", "state")
        if session == "burst":
            return os.path.join(PROJECT_ROOT, "runtime", "state_burst")
        return os.path.join(PROJECT_ROOT, "runtime", f"state_{session}")

    def running_mode(self, session: str) -> bool:
        """Check if a specific session's orchestrator is alive."""
        p = self.processes.get(session)
        return p is not None and p.is_alive()

    def running_session(self, session: str) -> bool:
        """Alias of running_mode (sessions replaced fixed modes)."""
        return self.running_mode(session)

    @property
    def running(self) -> bool:
        return any(p.is_alive() for p in self.processes.values())

    def any_running(self) -> List[str]:
        """Return list of sessions with live processes."""
        return [m for m, p in self.processes.items() if p.is_alive()]

    def _pid_file(self, session: str) -> str:
        state_dir = (self.configs.get(session) or {}).get(
            "state_dir", self._default_state_dir(session))
        return os.path.join(state_dir, "orchestrator.pid")

    def _write_pid(self, session: str):
        pid = self.processes[session].pid
        pid_file = self._pid_file(session)
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)
        with open(pid_file, "w") as f:
            f.write(str(pid))

    def _clear_pid(self, session: str):
        pid_file = self._pid_file(session)
        try:
            os.remove(pid_file)
        except OSError:
            pass

    def detect_orphans(self) -> Dict[str, int]:
        """Detect orphan orchestrator processes from PID files (all sessions)."""
        import glob
        active = {}
        pid_files = glob.glob(os.path.join(PROJECT_ROOT, "runtime",
                                           "state", "orchestrator.pid"))
        pid_files += glob.glob(os.path.join(PROJECT_ROOT, "runtime",
                                            "state_*", "orchestrator.pid"))
        for pid_file in pid_files:
            dirname = os.path.basename(os.path.dirname(pid_file))
            session = ("classic" if dirname == "state"
                       else dirname[len("state_"):] if dirname.startswith("state_")
                       else dirname)
            if os.path.exists(pid_file):
                try:
                    pid = int(open(pid_file).read().strip())
                    os.kill(pid, 0)  # check alive
                    active[session] = pid
                except (OSError, ValueError):
                    try:
                        os.remove(pid_file)
                    except OSError:
                        pass
        return active

    def stats_for(self, session: str) -> Dict:
        cfg = self.configs.get(session) or {}
        state_dir = cfg.get("state_dir", self._default_state_dir(session))
        stats_path = os.path.join(state_dir, "runtime_stats.json")
        if not os.path.exists(stats_path):
            return {"state": "RUNNING" if self.running_mode(session) else "STOPPED"}
        try:
            with open(stats_path) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}

    @property
    def stats(self) -> Dict:
        """Stats of first running session, else first known config."""
        for session in self.any_running():
            return self.stats_for(session)
        for session in self.configs:
            return self.stats_for(session)
        return {}

    @property
    def config_dict(self) -> Optional[Dict]:
        """Config of first running session, else first known config."""
        for session in self.any_running():
            return self.configs.get(session)
        for session in self.configs:
            return self.configs.get(session)
        return None

    def start(self, config_dict: Dict, mode: str = "classic",
              session: Optional[str] = None):
        self._ensure_pg_vm()
        os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")

        session = _sanitize_session(
            session or config_dict.get("session") or mode)
        mode = config_dict.get("mode", mode)

        # Stop existing process for this session if any (same-name restart)
        if self.running_mode(session):
            self.stop_mode(session)

        self.configs[session] = config_dict

        # Launch as fully detached subprocess (survives Termux close)
        launcher = os.path.join(PROJECT_ROOT, "quant_math_bg.py")
        config_json = json.dumps(config_dict)

        proc = subprocess.Popen(
            [sys.executable, "-u", launcher, config_json, mode],
            start_new_session=True,    # new process group — survives parent exit
            stdin=subprocess.DEVNULL,   # no terminal input
            stdout=subprocess.DEVNULL,  # output goes to log file
            stderr=subprocess.DEVNULL,
        )
        # Store as a simple object with .pid and .is_alive()
        self.processes[session] = _DetachedProcess(proc.pid, session)
        self._write_pid(session)

    def stop_mode(self, mode: str, timeout: float = 15.0) -> bool:
        """Stop a specific mode's orchestrator."""
        proc = self.processes.get(mode)
        if proc is None:
            self._clear_pid(mode)
            return False
        if not proc.is_alive():
            self._clear_pid(mode)
            return False
        # Escalating stop: SIGINT → SIGTERM → SIGKILL
        try:
            os.kill(proc.pid, signal.SIGINT)
        except (ProcessLookupError, OSError):
            pass
        time.sleep(2)
        if proc.is_alive():
            try:
                os.kill(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            time.sleep(2)
        if proc.is_alive():
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            time.sleep(1)
        self._force_stats_stopped(mode)
        self._clear_pid(mode)
        return True

    def stop_all(self, timeout: float = 15.0) -> bool:
        stopped = False
        for mode in list(self.processes):
            if self.stop_mode(mode, timeout):
                stopped = True
        return stopped

    def stop(self, timeout: float = 15.0) -> bool:
        """Legacy: stop all processes."""
        return self.stop_all(timeout)

    def _force_stats_stopped(self, session: str):
        """Best-effort: reflect STOPPED in runtime_stats.json."""
        cfg = self.configs.get(session) or {}
        state_dir = cfg.get("state_dir", self._default_state_dir(session))
        stats_path = os.path.join(state_dir, "runtime_stats.json")
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
            if lo is not None and val < lo:
                console.print(f"[red]Debe ser >= {lo}[/red]")
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


def _ask_market() -> Optional[str]:
    """Asset class: crypto (Bybit) or forex (Yahoo Finance)."""
    return questionary.select(
        "Clase de activo:",
        choices=[
            questionary.Choice("Crypto (Bybit, datos reales)", value="crypto"),
            questionary.Choice("Forex (Yahoo Finance, datos reales)", value="forex"),
        ]).unsafe_ask()


def _normalize_checkbox(result) -> list:
    """questionary.checkbox returns list or tuple depending on version."""
    if isinstance(result, tuple):
        return list(result[0]) if result and result[0] else []
    if isinstance(result, list):
        return result
    return list(result) if result else []


def _ask_symbols(market: str) -> Optional[List[str]]:
    """Symbol selection shared by classic/burst wizards."""
    if market == "forex":
        from data_acquisition.data_sources.forex import MAJORS
        use_top = questionary.select(
            "Selección de pares:",
            choices=[
                questionary.Choice("Majors (recomendado)", value="majors"),
                questionary.Choice("Ingresar manualmente (ej. EUR/USD)",
                                   value="manual"),
            ]).unsafe_ask()
        if use_top is None:
            return None
        if use_top == "majors":
            console.print("[cyan]Pares majors disponibles:[/cyan]")
            try:
                selected = _normalize_checkbox(questionary.checkbox(
                    "Selecciona pares (espacio marcar, Enter confirmar):",
                    choices=[questionary.Choice(s, value=s) for s in MAJORS]
                ).unsafe_ask())
            except (AttributeError, TypeError):
                return None
            if not selected:
                console.print("[red]Debes seleccionar al menos un par[/red]")
                return None
            return selected
        raw = questionary.text(
            "Pares (separados por coma, formato EUR/USD):",
            default="EUR/USD").unsafe_ask()
        if raw is None:
            return None
        symbols = []
        for s in raw.split(","):
            s = s.strip().upper().replace(" ", "")
            if not s:
                continue
            if "/" not in s and len(s) == 6:
                s = s[:3] + "/" + s[3:]
            if "/" not in s:
                console.print(f"[red]Par inválido: {s} (usa formato EUR/USD)[/red]")
                return None
            symbols.append(s)
        if not symbols:
            console.print("[red]Se requiere al menos un par[/red]")
            return None
        return symbols

    # Crypto path (Bybit Top-20 or manual)
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
            selected = _normalize_checkbox(questionary.checkbox(
                "Selecciona símbolos (espacio marcar, Enter confirmar):",
                choices=[questionary.Choice(s, value=s) for s in top_assets]
            ).unsafe_ask())
        except (AttributeError, TypeError):
            return None
        if not selected:
            console.print("[red]Debes seleccionar al menos un símbolo[/red]")
            return None
        return selected

    symbols_raw = questionary.text(
        "Símbolos (separados por coma):",
        default="BTC/USDT").unsafe_ask()
    if symbols_raw is None:
        return None
    symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
    if not symbols:
        console.print("[red]Se requiere al menos un símbolo[/red]")
        return None
    return symbols


def _ask_leverage_forex(symbol: str) -> Optional[int]:
    """Interactive FX leverage ladder (spot brokers offer up to 500x)."""
    from data_acquisition.data_sources.forex import FOREX_LEVERAGE_LEVELS
    use_lev = questionary.select(
        f"Operar con apalancamiento para {symbol}?",
        choices=[
            questionary.Choice("No (sin apalancamiento)", value=False),
            questionary.Choice("Sí", value=True),
        ]).unsafe_ask()
    if use_lev is None:
        return None
    if not use_lev:
        return 1
    lev = questionary.select(
        f"Nivel de apalancamiento (máx 500x spot FX para {symbol}):",
        choices=[questionary.Choice(f"{lv}x", value=lv)
                 for lv in FOREX_LEVERAGE_LEVELS],
        default=10).unsafe_ask()
    if lev is None:
        return None
    return lev


def _clamp_lookback(market: str, timeframe: str, lookback: int) -> int:
    """Yahoo intraday history is limited — clamp forex lookback per timeframe."""
    if market != "forex":
        return lookback
    from data_acquisition.data_sources.forex import MAX_LOOKBACK_DAYS
    mx = MAX_LOOKBACK_DAYS.get(timeframe, 30)
    if lookback > mx:
        console.print(f"[yellow]Lookback {lookback}d > máx Yahoo {timeframe} "
                      f"({mx}d) — ajustado a {mx}[/yellow]")
        return mx
    return lookback


def _sanitize_session(name: str) -> str:
    """Session names become directory/file suffixes: [a-z0-9_-] only."""
    import re
    s = re.sub(r"[^a-z0-9_-]", "-", (name or "").strip().lower())
    s = re.sub(r"-{2,}", "-", s).strip("-_")
    return s or "session"


def _session_paths(session: str):
    """(state_dir, kb_path, log_path) for a session.

    Legacy names keep legacy paths: classic -> state/, burst -> state_burst/.
    New sessions are isolated: state_<session>/, hypotheses_<session>.jsonl.
    """
    session = _sanitize_session(session)
    if session == "classic":
        state_dir = os.path.join(PROJECT_ROOT, "runtime", "state")
        kb_path = os.path.join(PROJECT_ROOT, "runtime", "hypotheses.jsonl")
        log_path = LOG_PATH
    elif session == "burst":
        state_dir = os.path.join(PROJECT_ROOT, "runtime", "state_burst")
        kb_path = os.path.join(PROJECT_ROOT, "runtime",
                               "hypotheses_burst.jsonl")
        log_path = BURST_LOG_PATH
    else:
        state_dir = os.path.join(PROJECT_ROOT, "runtime", f"state_{session}")
        kb_path = os.path.join(PROJECT_ROOT, "runtime",
                               f"hypotheses_{session}.jsonl")
        log_path = os.path.join(PROJECT_ROOT, f"quant_math_{session}.log")
    os.makedirs(state_dir, exist_ok=True)
    return state_dir, kb_path, log_path


def _ask_session_name(mode: str, symbols: List[str]) -> Optional[str]:
    """Name for this background session (isolated state/KB/log)."""
    base = (symbols[0] if symbols else "multi").replace("/USDT", "")
    base = base.replace("/", "")
    default = _sanitize_session(f"{mode}-{base}")
    raw = questionary.text(
        "Nombre de sesión (una por activo/modo, Enter para default):",
        default=default).unsafe_ask()
    if raw is None:
        return None
    return _sanitize_session(raw) or default


def _session_mode(runtime: "RuntimeState", session: str) -> str:
    """classic/burst layout for a session (from its config, legacy fallback)."""
    cfg = (runtime.configs.get(session) or {})
    mode = cfg.get("mode")
    if mode in ("classic", "burst"):
        return mode
    if session == "burst":
        return "burst"
    return "classic"


def wizard() -> Optional[Dict]:
    """Interactive configuration wizard. Returns cfg dict or None if cancelled."""
    console.print(Panel("[bold cyan]Wizard de configuración[/bold cyan]\n"
                        "Los datos de mercado son SIEMPRE reales "
                        "(Bybit crypto / Yahoo forex). "
                        "El modo es paper trading.", expand=False))
    try:
        market = _ask_market()
        if market is None:
            return None
        exchange_id = "yahoo" if market == "forex" else "bybit"

        symbols = _ask_symbols(market)
        if symbols is None:
            return None

        initial_capital = ask_float("Capital inicial (USD)", "50", lo=0)
        if initial_capital is None:
            return None

        # Leverage selection (per first symbol, applied to all)
        if market == "forex":
            leverage = _ask_leverage_forex(symbols[0])
        else:
            leverage = ask_leverage(symbols[0], "bybit", "classic")
        if leverage is None:
            return None

        entry_pct = ask_float("% de capital por entrada (0-1]", "0.02", hi=1)
        if entry_pct is None:
            return None
        timeframe = questionary.select(
            "Timeframe:", choices=["1m", "5m", "15m", "1h", "4h", "1d"],
            default="1h" if market == "crypto" else "15m").unsafe_ask()
        if timeframe is None:
            return None
        take_profit_pct = ask_float(
            "Take-profit % (ej. 0.25 = 25%)",
            "0.25" if market == "crypto" else "0.005")
        if take_profit_pct is None:
            return None
        lookback_days = ask_int("Lookback days (backtest)",
                                "30" if market == "crypto" else "14", lo=1)
        if lookback_days is None:
            return None
        lookback_days = _clamp_lookback(market, timeframe, lookback_days)
        hypotheses_per_cycle = ask_int("Hipótesis nuevas por ciclo", "3", lo=1)
        if hypotheses_per_cycle is None:
            return None

        exec_flags = _ask_execution_mode(initial_capital)
        if exec_flags is None:
            return None

        session = _ask_session_name("classic", symbols)
        if session is None:
            return None
        state_dir, kb_path, log_path = _session_paths(session)

        return {
            "session": session,
            "market": market,
            "symbols": symbols,
            "timeframe": timeframe,
            "lookback_days": lookback_days,
            "initial_capital": initial_capital,
            "entry_pct": entry_pct,
            "take_profit_pct": take_profit_pct,
            "min_paper_trades": 3,          # contract value; explicit on purpose
            "hypotheses_per_cycle": hypotheses_per_cycle,
            "kb_path": kb_path,
            "state_dir": state_dir,
            "log_path": log_path,
            "interval_seconds": 60,
            "exchange_id": exchange_id,
            "dry_run": exec_flags["dry_run"],
            "testnet": exec_flags["testnet"],
            "shadow_live": exec_flags["shadow_live"],
            "leverage": leverage,
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
        "Modo paper trading. Los datos son SIEMPRE reales "
        "(Bybit crypto / Yahoo forex).",
        expand=False))
    try:
        market = _ask_market()
        if market is None:
            return None
        exchange_id = "yahoo" if market == "forex" else "bybit"

        symbols = _ask_symbols(market)
        if symbols is None:
            return None

        margin = ask_float("Margen por entrada (USD, min 1)", "1", lo=1)
        if margin is None:
            return None

        # Leverage selection (per first symbol, applied to all)
        if market == "forex":
            leverage = _ask_leverage_forex(symbols[0])
        else:
            leverage = ask_leverage(symbols[0], "bybit", "burst")
        if leverage is None:
            return None

        timeframe = questionary.select(
            "Timeframe:", choices=["1m", "5m", "15m", "1h"],
            default="5m").unsafe_ask()
        if timeframe is None:
            return None

        tp_pct = ask_float("Take-profit % (ej. 0.20 = 20%)",
                           "0.20" if market == "crypto" else "0.005")
        if tp_pct is None:
            return None

        lookback_days = ask_int("Lookback days (backtest)", "14", lo=1)
        if lookback_days is None:
            return None
        lookback_days = _clamp_lookback(market, timeframe, lookback_days)
        hyp_per_cycle = ask_int("Hipótesis nuevas por ciclo", "5", lo=1)
        if hyp_per_cycle is None:
            return None

        exec_flags = _ask_execution_mode(50.0)
        if exec_flags is None:
            return None

        session = _ask_session_name("burst", symbols)
        if session is None:
            return None
        state_dir, kb_path, log_path = _session_paths(session)

        return {
            "session": session,
            "market": market,
            "symbols": symbols,
            "timeframe": timeframe,
            "lookback_days": lookback_days,
            "initial_capital": 50.0,
            "entry_pct": 0.1,               # ignored in burst mode (margin-based)
            "take_profit_pct": tp_pct,
            "min_paper_trades": 3,
            "hypotheses_per_cycle": hyp_per_cycle,
            "kb_path": kb_path,
            "state_dir": state_dir,
            "log_path": log_path,
            "interval_seconds": 15,
            "exchange_id": exchange_id,
            "dry_run": exec_flags["dry_run"],
            "testnet": exec_flags["testnet"],
            "shadow_live": exec_flags["shadow_live"],
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
_exchange_instances: Dict[str, object] = {}


def _get_exchange(exchange_id: str, market: str = "crypto"):
    """Get or create a shared market-data instance (ccxt or Yahoo FX)."""
    key = f"{market}:{exchange_id}"
    if key not in _exchange_instances:
        if (market or "crypto").lower() == "forex" or exchange_id == "yahoo":
            from data_acquisition.data_sources.forex import ForexAPI
            _exchange_instances[key] = ForexAPI()
        else:
            import ccxt
            _exchange_instances[key] = getattr(ccxt, exchange_id)({
                "enableRateLimit": True,
                "timeout": 5000,
            })
    return _exchange_instances[key]


def _get_current_price(symbol: str, exchange_id: str,
                       market: str = "crypto") -> Optional[float]:
    """Real price lookup with 5s cache per symbol."""
    cached = _price_cache.get(symbol)
    now = time.time()
    if cached and now - cached[1] < 5:
        return cached[0]
    try:
        ex = _get_exchange(exchange_id, market)
        ticker = ex.fetch_ticker(symbol)
        price = ticker.get("last") or ticker.get("close")
        if price:
            _price_cache[symbol] = (float(price), now)
            return float(price)
        return cached[0] if cached else None
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"Price fetch failed for {symbol}: {e}")
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


def get_max_leverage(exchange_id: str, symbol: str) -> int:
    """Fetch max leverage from Bybit for a given symbol. Returns 20 on error."""
    try:
        import ccxt
        ex = getattr(ccxt, exchange_id)({"enableRateLimit": True})
        ex.load_markets()
        # Try both formats: BTC/USDT and BTC/USDT:USDT
        market_sym = symbol
        if ":" not in symbol and symbol.endswith("/USDT"):
            market_sym = symbol + ":USDT"
        if market_sym in ex.markets:
            lev = ex.markets[market_sym].get("limits", {}).get("leverage", {})
            max_lev = lev.get("max", 20)
            return int(max_lev) if max_lev else 20
        return 20
    except Exception:
        return 20


def ask_leverage(symbol: str, exchange_id: str = "bybit", mode: str = "classic") -> Optional[int]:
    """Ask user if they want leverage, then show interactive level selection."""
    use_lev = questionary.select(
        f"Operar con apalancamiento para {symbol}?",
        choices=[
            questionary.Choice("No (sin apalancamiento)", value=False),
            questionary.Choice("Sí", value=True),
        ]).unsafe_ask()
    if use_lev is None:
        return None
    if not use_lev:
        return 1

    max_lev = get_max_leverage(exchange_id, symbol)
    # Build sensible leverage levels up to max
    standard_levels = [1, 2, 3, 5, 10, 15, 20, 25, 50, 75, 100, 125, 150]
    levels = [l for l in standard_levels if l <= max_lev]
    if not levels:
        levels = [1]
    if max_lev not in levels:
        levels.append(max_lev)

    choices = [questionary.Choice(f"{l}x", value=l) for l in levels]
    default_lev = 10 if 10 in levels else levels[0]
    lev = questionary.select(
        f"Nivel de apalancamiento (máx {max_lev}x para {symbol}):",
        choices=choices,
        default=default_lev).unsafe_ask()
    if lev is None:
        return None
    return lev


def _ask_execution_mode(initial_capital: float) -> Optional[Dict]:
    """Ask paper / testnet-live / mainnet-live. Returns execution flags.

    - paper: dry_run=True (default, no keys needed).
    - testnet: dry_run=False + testnet=True + shadow log. Requires .env keys.
    - mainnet: dry_run=False + testnet=False. Requires
      QUANTMATH_ALLOW_MAINNET=1 in env + .env keys + double confirmation.
    Returns None if cancelled or requirements unmet.
    """
    from data_acquisition.data_sources.exchanges import api_keys_present
    mode = questionary.select(
        "Modo de ejecución:",
        choices=[
            questionary.Choice("Paper trading (recomendado)", value="paper"),
            questionary.Choice("Testnet live (Bybit Testnet, requiere API keys)",
                               value="testnet"),
            questionary.Choice("Mainnet live (DINERO REAL, doble confirmación)",
                               value="mainnet"),
        ]).unsafe_ask()
    if mode is None or mode == "paper":
        return {"dry_run": True, "testnet": True, "shadow_live": False}
    if not api_keys_present():
        console.print("[red]Modo live requiere BYBIT_API_KEY y BYBIT_API_SECRET "
                      "en .env (ver .env.example)[/red]")
        return None
    if mode == "testnet":
        ok = questionary.confirm(
            "Confirmar trading REAL en TESTNET (sin dinero real)?",
            default=False).unsafe_ask()
        if not ok:
            return None
        console.print("[yellow]Testnet live activado + shadow log.[/yellow]")
        return {"dry_run": False, "testnet": True, "shadow_live": True}
    # mainnet — Fase 4
    if os.environ.get("QUANTMATH_ALLOW_MAINNET") != "1":
        console.print("[red]Mainnet bloqueado por diseño: exporta "
                      "QUANTMATH_ALLOW_MAINNET=1 primero[/red]")
        return None
    console.print(f"[bold red]VAS A OPERAR CON DINERO REAL "
                  f"(capital ${initial_capital:.2f}).[/bold red]")
    ok1 = questionary.confirm("Confirmación 1/2: ¿entendido el riesgo?",
                              default=False).unsafe_ask()
    if not ok1:
        return None
    ok2 = questionary.confirm("Confirmación 2/2: ¿iniciar mainnet live?",
                              default=False).unsafe_ask()
    if not ok2:
        return None
    return {"dry_run": False, "testnet": False, "shadow_live": True}


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


def render_monitor(runtime: RuntimeState, mode: str = "classic"):
    stats = runtime.stats_for(mode)
    cfg = stats.get("config", {})
    state_dir = cfg.get("state_dir", "runtime/state")
    state = "RUNNING" if runtime.running_mode(mode) else "STOPPED"

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
    trades = _read_paper_trades(state_dir)
    # Two-pass: first collect closure keys, then count open entries correctly.
    closed_keys = set()
    total_closed = wins = losses = 0
    realized = realized_legacy = 0.0
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
    open_entries = [
        rec for rec in trades
        if "motivo_cierre" not in rec
        and rec.get("key") not in closed_keys
        and not (cutoff and float(rec.get("timestamp") or 0) < cutoff)
    ]
    unrealized = 0.0
    for t in open_entries:
        cur = _get_current_price(t["symbol"], cfg.get("exchange_id", "bybit"), cfg.get("market", "crypto"))
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
                "mode", "leverage"):
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


def monitor_loop(runtime: RuntimeState, mode: str = "classic"):
    """Live monitor; ESC returns to menu without stopping anything."""
    console.print("[dim]Monitor en vivo — presiona ESC para volver al menú[/dim]")
    try:
        with Live(render_monitor(runtime, mode), console=console, refresh_per_second=2,
                  screen=False, redirect_stdout=False, redirect_stderr=False) as live:
            while True:
                live.update(render_monitor(runtime, mode))
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


def view_history(runtime: RuntimeState, state_dir: Optional[str] = None):
    from quant_math.ml.feature_store import integration_cutoff
    if state_dir is None:
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

def view_burst_history(state_dir: Optional[str] = None):
    state_dir = state_dir or BURST_STATE_DIR
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


def render_burst_monitor(runtime: RuntimeState, mode: str = "burst"):
    stats = runtime.stats_for(mode)
    cfg = stats.get("config", {})
    state_dir = cfg.get("state_dir", BURST_STATE_DIR)
    state = "RUNNING" if runtime.running_mode(mode) else "STOPPED"

    header = Table.grid(padding=(0, 2))
    header.add_column(justify="left")
    header.add_row(Text("BURST SCALPING MONITOR", style="bold cyan"))
    status = Text(f"● {state}", style="bold green" if state == "RUNNING" else "bold red")
    cycles = stats.get("cycles_completed", 0)
    generated = stats.get("hypotheses_generated", 0)

    open_pos = _burst_count_open_positions()
    trades = _burst_read_paper_trades()
    # Two-pass: first collect closure keys, then count open entries correctly.
    closed_keys = set()
    total_closed = wins = losses = 0
    total_pnl = 0.0
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
    open_entries = [
        t for t in trades
        if "motivo_cierre" not in t
        and t.get("key") not in closed_keys
    ]
    win_rate = (wins / total_closed * 100) if total_closed else 0.0

    # MtM: fetch current prices for open entries
    unrealized = 0.0
    for t in open_entries:
        cur = _get_current_price(t["symbol"], cfg.get("exchange_id", "bybit"), cfg.get("market", "crypto"))
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
                "mode", "burst_margin", "burst_leverage", "leverage"):
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


def burst_monitor_loop(runtime: RuntimeState, mode: str = "burst"):
    """Live burst monitor; ESC returns to menu without stopping anything."""
    console.print("[dim]Burst monitor — presiona ESC para volver al menú[/dim]")
    try:
        with Live(render_burst_monitor(runtime, mode), console=console,
                  refresh_per_second=1, screen=False,
                  redirect_stdout=False, redirect_stderr=False) as live:
            while True:
                live.update(render_burst_monitor(runtime, mode))
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
    if runtime.running and not runtime._minimized:
        console.print("[yellow]Deteniendo orchestrators...[/yellow]")
        runtime.stop_all()
        console.print("[green]Orchestrators detenidos.[/green]")
    elif runtime._minimized and runtime.running:
        console.print("[dim]Procesos siguen en background (minimizados).[/dim]")

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


def _detect_active_modes(runtime: RuntimeState) -> Dict[str, int]:
    """Detect running sessions from PID files (for re-entrant CLI)."""
    orphans = runtime.detect_orphans()
    for session, pid in orphans.items():
        if not runtime.running_mode(session):
            # Register orphan so it can be stopped from the menu
            runtime.processes[session] = _DetachedProcess(pid, session)
            console.print(f"[green]Sesión {session} detectada (PID {pid}) — "
                          "registrada para control desde el menú.[/green]")
    return orphans


def _session_label(runtime: RuntimeState, session: str) -> str:
    """Human label for a session: mode + market + symbols."""
    cfg = runtime.configs.get(session) or {}
    mode = cfg.get("mode", "burst" if session == "burst" else "classic")
    base = "Quant-Math" if mode == "classic" else "Burst Scalping"
    market = cfg.get("market", "")
    symbols = ",".join(cfg.get("symbols", []) or [])
    extra = " ".join(p for p in [market, symbols] if p)
    return f"{base} [{session}]" + (f" {extra}" if extra else "")


def _ask_mode(runtime: RuntimeState, require_running: bool = True) -> Optional[str]:
    """Ask user to pick a session. Returns None on ESC."""
    running = runtime.any_running()
    if require_running and not running:
        return None
    try:
        choices = []
        for session in (running or list(runtime.configs)):
            is_up = runtime.running_mode(session)
            status = " ●" if is_up else ""
            choices.append(questionary.Choice(
                f"{_session_label(runtime, session)}{status}", value=session))
        if not choices:
            return None
        return questionary.select("¿Qué sesión?", choices=choices).unsafe_ask()
    except (AttributeError):
        return None


def _clean_history(runtime: RuntimeState):
    """Archive and clean operation history files (all sessions)."""
    import glob
    import shutil
    # Check if any session is running
    if runtime.any_running():
        console.print("[red]Detené todas las sesiones antes de limpiar el historial.[/red]")
        return

    scope = questionary.select(
        "¿Qué historial limpiar?",
        choices=[
            questionary.Choice("Todas las sesiones", value="all"),
            questionary.Choice("Una sesión...", value="one"),
            questionary.Choice("Cancelar", value=None),
        ]).unsafe_ask()
    if scope is None:
        console.print("[dim]Cancelado.[/dim]")
        return

    state_dirs = sorted(glob.glob(os.path.join(PROJECT_ROOT, "runtime", "state")) +
                        glob.glob(os.path.join(PROJECT_ROOT, "runtime", "state_*")))
    kb_files = sorted(glob.glob(os.path.join(PROJECT_ROOT, "runtime",
                                             "hypotheses*.jsonl")))
    if scope == "one":
        options = [os.path.basename(d) for d in state_dirs]
        if not options:
            console.print("[yellow]No hay estado de sesiones.[/yellow]")
            return
        pick = questionary.select("¿Qué sesión limpiar?",
                                  choices=options).unsafe_ask()
        if pick is None:
            return
        state_dirs = [os.path.join(PROJECT_ROOT, "runtime", pick)]
        kb_files = [f for f in kb_files
                    if pick == "state" and f.endswith("hypotheses.jsonl")
                    or pick == "state_burst" and f.endswith("hypotheses_burst.jsonl")
                    or f.endswith(f"hypotheses_{pick[len('state_'):]}.jsonl")]

    confirm = questionary.select(
        "Esto archivará y limpiará las operaciones (activas, cerradas, KB). ¿Continuar?",
        choices=[
            questionary.Choice("No, cancelar", value=False),
            questionary.Choice("Sí, limpiar", value=True),
        ]).unsafe_ask()
    if not confirm:
        console.print("[dim]Cancelado.[/dim]")
        return

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(PROJECT_ROOT, "runtime", "archive", f"clean_{timestamp}")
    os.makedirs(archive_dir, exist_ok=True)

    names = ("paper_executions.jsonl", "paper_trades.jsonl", "positions.jsonl",
             "runtime_stats.json", "learning_meta.json", "graduation.json",
             "burst_state.json", "daily_pnl.json", "shadow_orders.jsonl")
    files_to_clean = []
    for d in state_dirs:
        for n in names:
            files_to_clean.append(os.path.join(d, n))
    files_to_clean.extend(kb_files)

    cleaned = 0
    for f in files_to_clean:
        if os.path.exists(f) and os.path.getsize(f) > 0:
            rel = os.path.relpath(f, os.path.join(PROJECT_ROOT, "runtime"))
            dest = os.path.join(archive_dir, rel.replace(os.sep, "__"))
            shutil.copy2(f, dest)
            with open(f, "w") as fh:
                pass
            cleaned += 1

    console.print(f"[green]Historial limpiado: {cleaned} archivos archivados en {archive_dir}[/green]")


def main():
    runtime = RuntimeState()
    # Detect orphan processes from previous sessions
    _detect_active_modes(runtime)

    try:
        while True:
            try:
                running = runtime.any_running()

                menu_choices = [
                    questionary.Choice("Iniciar Quant-Math", value="start"),
                    questionary.Choice("Iniciar Burst Scalping",
                                       value="start_burst"),
                ]
                for session in running:
                    menu_choices.append(questionary.Choice(
                        f"Detener {_session_label(runtime, session)}",
                        value=f"stop:{session}"))
                if running:
                    menu_choices.append(questionary.Choice(
                        f"Detener todos ({len(running)})", value="stop_all"))
                menu_choices += [
                    questionary.Choice("Monitor", value="monitor"),
                    questionary.Choice("Ver log", value="log"),
                    questionary.Choice("Historial de operaciones",
                                       value="history"),
                    questionary.Choice("Limpiar historial",
                                       value="clean_history"),
                    questionary.Choice("Minimizar (seguir en background)",
                                       value="minimize"),
                    questionary.Choice("Salir", value="quit"),
                ]
                action = questionary.select(
                    "QUANT-MATH — Menú principal  (↑/↓ + Enter)",
                    choices=menu_choices,
                ).unsafe_ask()
            except KeyboardInterrupt:
                print()
                shutdown(runtime)
                return 0

            if action is None:  # ESC on main menu
                if runtime.running:
                    console.print("[dim]ESC: sigue corriendo en fondo. "
                                  "Usa 'Salir' o 'Detener todos' para cerrar.[/dim]")
                continue

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
        session = cfg.get("session", "classic")
        runtime.start(cfg)
        pid = runtime.processes[session].pid
        console.print(f"[green]Sesión {session} iniciada (pid={pid}). "
                      f"Logs: {cfg.get('log_path', LOG_PATH)}[/green]")
        try:
            questionary.press_any_key_to_continue(message="(ENTER/tecla para volver)").unsafe_ask()
        except (AttributeError):
            pass

    elif action == "start_burst":
        cfg = burst_wizard()
        if cfg is None:
            console.print("[dim]Wizard burst cancelado.[/dim]")
            return
        session = cfg.get("session", "burst")
        runtime.start(cfg)
        pid = runtime.processes[session].pid
        console.print(f"[green]Sesión {session} iniciada (pid={pid}). "
                      f"Logs: {cfg.get('log_path', BURST_LOG_PATH)}[/green]")
        try:
            questionary.press_any_key_to_continue(message="(ENTER/tecla para volver)").unsafe_ask()
        except (AttributeError):
            pass

    elif action.startswith("stop:"):
        session = action[len("stop:"):]
        if runtime.stop_mode(session):
            console.print(f"[green]Sesión {session} detenida.[/green]")
        else:
            console.print(f"[yellow]Sesión {session} no está corriendo.[/yellow]")

    elif action == "stop_all":
        if runtime.stop_all():
            console.print("[green]Todos los procesos detenidos.[/green]")
        else:
            console.print("[yellow]No hay procesos activos.[/yellow]")

    elif action == "monitor":
        running = runtime.any_running()
        if len(running) == 0:
            console.print("[yellow]Ninguna sesión está corriendo. Iniciá una primero.[/yellow]")
            return
        elif len(running) == 1:
            session = running[0]
        else:
            session = _ask_mode(runtime, require_running=True)
            if session is None:
                return
        if _session_mode(runtime, session) == "burst":
            burst_monitor_loop(runtime, session)
        else:
            monitor_loop(runtime, session)

    elif action == "log":
        running = runtime.any_running()
        if len(running) == 0:
            view_log()
            return
        elif len(running) == 1:
            session = running[0]
        else:
            session = _ask_mode(runtime, require_running=False)
            if session is None:
                return
        cfg = runtime.configs.get(session) or {}
        view_log_path(cfg.get("log_path", LOG_PATH))

    elif action == "history":
        running = runtime.any_running()
        if len(running) == 0:
            view_history(runtime)
            return
        elif len(running) == 1:
            session = running[0]
        else:
            session = _ask_mode(runtime, require_running=False)
            if session is None:
                return
        cfg = runtime.configs.get(session) or {}
        state_dir = cfg.get("state_dir")
        if _session_mode(runtime, session) == "burst":
            view_burst_history(state_dir=state_dir)
        else:
            view_history(runtime, state_dir=state_dir)

    elif action == "clean_history":
        _clean_history(runtime)

    elif action == "minimize":
        running = runtime.any_running()
        if not running:
            console.print("[yellow]No hay procesos corriendo para minimizar.[/yellow]")
            return
        runtime._minimized = True
        console.print()
        console.print("[bold cyan]Minimizando — procesos en background:[/bold cyan]")
        for session in running:
            pid = runtime.processes[session].pid
            console.print(f"  ● {_session_label(runtime, session)}: PID {pid}")
        console.print()
        console.print("Para detener: abrí el menú de nuevo y elegí la sesión "
                      "o 'Detener todos'.")
        console.print()
        try:
            questionary.press_any_key_to_continue(message="(ENTER/tecla para volver)").unsafe_ask()
        except (AttributeError):
            pass

    elif action == "quit":
        shutdown(runtime)
        raise SystemExit(0)


if __name__ == "__main__":
    sys.exit(main())
