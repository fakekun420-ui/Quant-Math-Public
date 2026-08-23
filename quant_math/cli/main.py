"""
Quant-Math interactive CLI.

Menu:
  1. Iniciar Quant-Math   -> config wizard, then Orchestrator in a background PROCESS
  2. Detener investigación -> graceful stop of the background process
  3. Monitor               -> live rich dashboard (if running)
  4. Ver log               -> paginated quant_math.log viewer
  5. Salir

Logs from the orchestrator process go to quant_math.log ONLY — they never
mix with the Live monitor render.
"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import signal
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

console = Console()


# ---------------------------------------------------------------------------
# Background process target (module-level so it is picklable)
# ---------------------------------------------------------------------------

def _orchestrator_process_main(cfg_dict: Dict):
    """Child process: run the orchestrator loop with all output to quant_math.log."""
    # Route ALL stdout/stderr to the log file before importing heavy modules
    log_fh = open(LOG_PATH, "a", buffering=1)
    sys.stdout = log_fh
    sys.stderr = log_fh
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PATH)],
        force=True,
    )

    def _handle_sigint(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handle_sigint)

    from quant_math.orchestrator import Orchestrator, OrchestratorConfig

    config = OrchestratorConfig(**cfg_dict)
    orch = Orchestrator(config)
    try:
        orch.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        orch.mark_stopped()
        log_fh.close()


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

class RuntimeState:
    """Tracks the background orchestrator process."""

    def __init__(self):
        self.process: Optional[mp.Process] = None
        self.config_dict: Optional[Dict] = None

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
        self.config_dict = config_dict
        ctx = mp.get_context("spawn")
        self.process = ctx.Process(
            target=_orchestrator_process_main,
            args=(config_dict,),
            daemon=False,
            name="quant-math-orchestrator",
        )
        self.process.start()

    def stop(self, timeout: float = 30.0) -> bool:
        if not self.running:
            return False
        self.process.send_signal(signal.SIGINT)
        self.process.join(timeout=timeout)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
        return True


# ---------------------------------------------------------------------------
# Config wizard
# ---------------------------------------------------------------------------

def ask_float(label: str, default: str, lo: float = None, hi: float = None) -> float:
    while True:
        raw = questionary.text(f"{label}:", default=default).ask()
        if raw is None:  # ESC
            raise KeyboardInterrupt
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


def ask_int(label: str, default: str, lo: int = None) -> int:
    while True:
        raw = questionary.text(f"{label}:", default=default).ask()
        if raw is None:
            raise KeyboardInterrupt
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
        symbols_raw = questionary.text(
            "Símbolos a operar (separados por coma):",
            default="BTC/USDT").ask()
        if symbols_raw is None:
            return None
        symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
        if not symbols:
            console.print("[red]Se requiere al menos un símbolo[/red]")
            return None

        initial_capital = ask_float("Capital inicial (USD)", "10000", lo=0)
        entry_pct = ask_float("% de capital por entrada (0-1]", "0.05", hi=1)
        timeframe = questionary.select(
            "Timeframe:", choices=["1m", "5m", "15m", "1h", "4h", "1d"],
            default="1h").ask()
        if timeframe is None:
            return None
        take_profit_pct = ask_float("Take-profit % (ej. 0.02 = 2%)", "0.02")
        lookback_days = ask_int("Lookback days (backtest)", "30", lo=1)
        hypotheses_per_cycle = ask_int("Hipótesis nuevas por ciclo", "3", lo=1)

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
            "interval_seconds": 60,
            "exchange_id": "bybit",
            "dry_run": True,                # paper trading only
        }
    except (KeyboardInterrupt, AttributeError):
        # ESC / Ctrl+C during wizard -> back to menu
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


def render_monitor(runtime: RuntimeState):
    stats = runtime.stats
    cfg = stats.get("config", {})
    state = "RUNNING" if runtime.running else "STOPPED"

    header = Table.grid(padding=(0, 2))
    header.add_column(justify="left")
    header.add_row(Text("QUANT-MATH MONITOR", style="bold cyan"))
    status = Text(f"● {state}", style="bold green" if state == "RUNNING" else "bold red")
    cycles = stats.get("cycles_completed", 0)
    generated = stats.get("hypotheses_generated", 0)
    evaluated = stats.get("hypotheses_evaluated", 0)

    # Paper trade P&L (mark-to-market vs real prices, throttled)
    wins = losses = 0
    unrealized = 0.0
    trades = _read_paper_trades(runtime.config_dict["state_dir"]) \
        if runtime.config_dict else []
    for t in trades:
        cur = _get_current_price(t["symbol"], cfg.get("exchange_id", "bybit"))
        ref = cur if cur is not None else t["entry_price"]
        direction = 1 if t["side"] == "buy" else -1
        pnl = t["quantity"] * (ref - t["entry_price"]) * direction
        unrealized += pnl
        wins += pnl >= 0
        losses += pnl < 0

    equity = cfg.get("initial_capital", 0.0) + unrealized

    body = Table(show_header=True, header_style="bold magenta", expand=True)
    body.add_column("Métrica")
    body.add_column("Valor", justify="right")
    body.add_row("Estado", status)
    body.add_row("Ciclos completados", str(cycles))
    body.add_row("Hipótesis generadas", str(generated))
    body.add_row("Hipótesis evaluadas", str(evaluated))
    body.add_row("Operaciones tomadas",
                 f"[green]{wins} positivas[/green] / [red]{losses} negativas[/red]")
    pnl_style = "green" if unrealized >= 0 else "red"
    body.add_row("Beneficio/Pérdida (MtM)", Text(f"{unrealized:+,.2f} USD", style=pnl_style))
    body.add_row("Equity", f"${equity:,.2f}")
    body.add_row("Último ciclo",
                 time.strftime("%H:%M:%S", time.localtime(stats.get("last_cycle_at", 0)))
                 if stats.get("last_cycle_at") else "-")

    config_panel = Table.grid(padding=(0, 1))
    for key in ("symbols", "timeframe", "initial_capital", "entry_pct",
                "take_profit_pct", "lookback_days", "min_paper_trades",
                "hypotheses_per_cycle", "exchange_id", "mode"):
        if key in cfg:
            config_panel.add_row(key, str(cfg[key]))

    return Panel(
        Table.grid().add_row(body).add_row(
            Panel(config_panel, title="Config activa")),
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
                # Non-blocking ESC check
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
    except Exception as exc:  # non-tty fallback
        console.print(f"[yellow]Monitor no disponible sin TTY interactivo: {exc}[/yellow]")


# ---------------------------------------------------------------------------
# Log viewer
# ---------------------------------------------------------------------------

def view_log():
    if not os.path.exists(LOG_PATH):
        console.print("[yellow]Sin logs todavía (quant_math.log no existe)[/yellow]")
        return questionary.press_any_key_to_continue().ask()
    with open(LOG_PATH, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    page_size = 40
    total_pages = max(1, (len(lines) + page_size - 1) // page_size)
    page = max(0, total_pages - 1)  # start at the end (most recent)
    while True:
        chunk = lines[page * page_size:(page + 1) * page_size]
        text = "".join(chunk) or "(vacía)"
        console.print(Panel(text, title=f"quant_math.log — página {page + 1}/{total_pages}"))
        choice = questionary.select(
            "Log:",
            choices=[
                questionary.Choice("Siguiente página →", value="next"),
                questionary.Choice("← Página anterior", value="prev"),
                questionary.Choice("Volver al menú (ESC)", value="back"),
            ]).ask()
        if choice in (None, "back"):
            return
        if choice == "next" and page < total_pages - 1:
            page += 1
        elif choice == "prev" and page > 0:
            page -= 1


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def shutdown(runtime: RuntimeState):
    if runtime.running:
        console.print("[yellow]Deteniendo orchestrator...[/yellow]")
        runtime.stop(timeout=45)
        console.print("[green]Orchestrator detenido.[/green]")
    console.print("[bold]Hasta luego.[/bold]")


def main():
    runtime = RuntimeState()
    try:
        while True:
            action = questionary.select(
                "QUANT-MATH — Menú principal",
                choices=[
                    questionary.Choice("Iniciar Quant-Math",
                                       value="start",
                                       disabled="ya está corriendo" if runtime.running else None),
                    questionary.Choice("Detener investigación",
                                       value="stop",
                                       disabled="no está corriendo" if not runtime.running else None),
                    questionary.Choice("Monitor",
                                       value="monitor"),
                    questionary.Choice("Ver log",
                                       value="log"),
                    questionary.Choice("Salir", value="quit"),
                ],
            ).ask()

            if action is None:  # ESC on main menu
                if runtime.running:
                    console.print("[dim]ESC: sigue corriendo en fondo. "
                                  "Usa 'Salir' o 'Detener investigación' para cerrar.[/dim]")
                continue

            if action == "start":
                cfg = wizard()
                if cfg is None:
                    console.print("[dim]Wizard cancelado.[/dim]")
                    continue
                runtime.start(cfg)
                console.print(f"[green]Orchestrator iniciado en proceso de fondo "
                              f"(pid={runtime.process.pid}). Logs: {LOG_PATH}[/green]")
                questionary.press_any_key_to_continue(message="(ENTER/tecla para volver)").ask()

            elif action == "stop":
                if runtime.stop():
                    console.print("[green]Investigación detenida.[/green]")
                else:
                    console.print("[yellow]No hay proceso activo.[/yellow]")

            elif action == "monitor":
                monitor_loop(runtime)

            elif action == "log":
                view_log()

            elif action == "quit":
                shutdown(runtime)
                return 0

    except KeyboardInterrupt:
        print()
        shutdown(runtime)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
