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

    # Set learn mode
    os.environ.setdefault("QUANTMATH_LEARN_MODE", "1")

    from quant_math.orchestrator import Orchestrator, OrchestratorConfig

    config = OrchestratorConfig(**cfg_dict)
    orch = Orchestrator(config)

    _acquire_wakelock()
    try:
        orch.run_forever()
    finally:
        orch.mark_stopped()
        _release_wakelock()
        try:
            os.remove(pid_file)
        except OSError:
            pass
        cap.fh.close()


if __name__ == "__main__":
    main()
