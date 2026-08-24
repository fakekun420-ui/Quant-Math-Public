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

def ask_float(label: str, default: str, lo: float = None, hi: float = None) -> float:
    while True:
        raw = questionary.text(f"{label}:", default=default).unsafe_ask()
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
        raw = questionary.text(f"{label}:", default=default).unsafe_ask()
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
            default="BTC/USDT").unsafe_ask()
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
            default="1h").unsafe_ask()
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
    except (AttributeError):
        # ESC / pregunta cancelada -> volver al menú.
        # KeyboardInterrupt NO se captura: Ctrl+C = cierre total del sistema.
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


def _count_open_positions(state_dir: str) -> int:
    path = os.path.join(state_dir, "positions.jsonl")
    if not os.path.exists(path):
        return 0
    return sum(1 for line in open(path, encoding="utf-8") if line.strip())


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
    # entradas que siguen vivas (sin closure posterior para su key)
    trades = _read_paper_trades(state_dir) if runtime.config_dict else []
    closed_keys = set()
    total_closed = wins = losses = 0
    realized = 0.0
    open_entries = []
    for rec in trades:
        if "motivo_cierre" in rec:
            total_closed += 1
            pnl = float(rec.get("pnl", 0.0))
            realized += pnl
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            if rec.get("key"):
                closed_keys.add(rec["key"])
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
    body.add_row("Equity", f"${equity:,.2f}")
    body.add_row("Último ciclo",
                 time.strftime("%H:%M:%S", time.localtime(stats.get("last_cycle_at", 0)))
                 if stats.get("last_cycle_at") else "-")

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
    if not os.path.exists(LOG_PATH):
        console.print("[yellow]Sin logs todavía (quant_math.log no existe)[/yellow]")
        return questionary.press_any_key_to_continue().unsafe_ask()
    with open(LOG_PATH, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    page_size = 40
    total_pages = max(1, (len(lines) + page_size - 1) // page_size)
    page = max(0, total_pages - 1)  # start at the end (most recent)
    while True:
        chunk = lines[page * page_size:(page + 1) * page_size]
        text = "".join(chunk) or "(vacía)"
        console.print(Panel(text, title=f"quant_math.log — página {page + 1}/{total_pages}"))
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
            # ESC -> volver al menú; Ctrl+C propaga (cierre total)
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
    state_dir = (runtime.config_dict or {}).get(
        "state_dir", os.path.join(PROJECT_ROOT, "runtime", "state"))
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
                str(c.get("motivo_cierre", "")))
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

    elif action == "monitor":
        monitor_loop(runtime)

    elif action == "log":
        view_log()

    elif action == "history":
        view_history(runtime)

    elif action == "quit":
        shutdown(runtime)
        raise SystemExit(0)


if __name__ == "__main__":
    sys.exit(main())
