#!/usr/bin/env python3
"""
Quant-Math Background Launcher.

Standalone script that runs the orchestrator as a fully detached process.
Invoked by the CLI via subprocess.Popen with start_new_session=True.
Writes PID file, redirects output to log, and runs forever.

Usage:
    python quant_math_bg.py <config_json> <mode>
"""
import json
import os
import signal
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
import logging


def main():
    if len(sys.argv) < 3:
        print("Usage: quant_math_bg.py <config_json> <mode>", file=sys.stderr)
        sys.exit(1)

    config_json = sys.argv[1]
    mode = sys.argv[2]

    cfg_dict = json.loads(config_json)

    # RuntimeState envía claves de gestión de sesión (session, log_path)
    # que no pertenecen a OrchestratorConfig — se descartan aquí.
    # Sin este pop, toda sesión con nombre muere al nacer con:
    #   TypeError: OrchestratorConfig.__init__() got an unexpected
    #   keyword argument 'session' (ver quant_math_<session>.log).
    cfg_dict.pop("session", None)

    # Termux wakelock
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

    # Lower process priority
    try:
        os.nice(10)
    except (OSError, AttributeError):
        pass

    # Write PID file
    state_dir = cfg_dict.get("state_dir", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "runtime",
        f"state_{mode}" if mode == "burst" else "state"))
    os.makedirs(state_dir, exist_ok=True)
    pid_file = os.path.join(state_dir, "orchestrator.pid")
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    # Setup logging to file
    log_path = cfg_dict.pop("log_path", os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "quant_math_burst.log" if mode == "burst" else "quant_math.log"))

    class _CappedStream:
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
        orch.request_stop()

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)

    # Gate de decision (correccion no3, 2026-09-29): aqui NO se enciende
    # nada. Esta linea hacia `setdefault("QUANTMATH_LEARN_MODE", "1")`, que
    # gana siempre que la variable no exista, y como este es el UNICO
    # camino de produccion el gate expectancy>0 nunca estuvo cerrado
    # (5 de 5 operaciones con expectancy negativa en el run real, F3).
    #
    # Ahora la exploracion solo se activa si el operador la pide de forma
    # EXPLICITA: `learn_mode` en la config del wizard o
    # QUANTMATH_LEARN_MODE=1 en el entorno. Si no se pide, la variable se
    # deja como estuviera y la politica (quant_math/risk/gate_policy.py)
    # resuelve GATE CERRADO. La resolucion queda registrada en
    # <state_dir>/learn_mode_audit.jsonl.
    _learn_requested = cfg_dict.get("learn_mode")
    if _learn_requested is not None:
        os.environ["QUANTMATH_LEARN_MODE"] = (
            "1" if _learn_requested else "0")
        print(f"[gate] learn_mode={bool(_learn_requested)} pedido "
              f"explicitamente en la config")
    else:
        print("[gate] learn_mode NO pedido: gate expectancy>0 CERRADO "
              "(igual que el motor; la exploracion hay que pedirla)")

    from quant_math.orchestrator import Orchestrator, OrchestratorConfig

    config = OrchestratorConfig(**cfg_dict)
    orch = None
    try:
        orch = Orchestrator(config)
    except Exception:
        # __init__ puede fallar (datos/API/estado) — nunca dejar PID stale.
        # Sin este guard, el PID file sobrevive al crash y la sesión aparece
        # "corriendo" en el menú aunque el proceso murió (menú congelado).
        try:
            os.remove(pid_file)
        except OSError:
            pass
        raise

    _acquire_wakelock()
    try:
        orch.run_forever()
    finally:
        if orch is not None:
            try:
                orch.mark_stopped()
            except Exception:
                pass
        _release_wakelock()
        try:
            os.remove(pid_file)
        except OSError:
            pass
        cap.fh.close()


if __name__ == "__main__":
    main()
