"""Run STT and TTS services concurrently.

Usage examples:
  # Run both services with defaults from config.yaml
  python run_services.py

  # Run only the STT service on custom port
  python run_services.py --only stt --stt-port 8011

  # Run TTS on localhost only
  python run_services.py --only tts --tts-host 127.0.0.1

  # Custom host and port for both services
  python run_services.py --stt-host 0.0.0.0 --stt-port 9010 --tts-host 0.0.0.0 --tts-port 9000

This script uses subprocess to spawn each uvicorn server in its
own process which avoids event-loop interference and is cross-platform.
"""
from __future__ import annotations

import argparse
import subprocess
import signal
import sys
import time
import logging
from typing import Optional
from pathlib import Path

from core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s"
)


def start_service(app_module: str, host: str, port: int) -> subprocess.Popen:
    """Start a service using uvicorn in a subprocess."""
    # Use venv Python if available, otherwise use system Python
    base_dir = Path(__file__).parent
    venv_python = base_dir / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable
    
    cmd = [
        python_exe,
        "-m",
        "uvicorn",
        app_module,
        "--host", host,
        "--port", str(port),
        "--log-level", "info"
    ]
    logger.info(f"Starting {app_module} on {host}:{port}")
    return subprocess.Popen(cmd, cwd=str(base_dir))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run STT and TTS services")
    parser.add_argument("--stt-host", default=settings.STT_HOST, help="STT server host")
    parser.add_argument("--stt-port", type=int, default=settings.STT_PORT, help="STT server port")
    parser.add_argument("--tts-host", default=settings.TTS_HOST, help="TTS server host")
    parser.add_argument("--tts-port", type=int, default=settings.TTS_PORT, help="TTS server port")
    parser.add_argument(
        "--only",
        choices=("stt", "tts", "both"),
        default="both",
        help="Which service(s) to run"
    )

    args = parser.parse_args(argv)

    procs = []

    def signal_handler(sig, frame):
        """Handle SIGINT/SIGTERM gracefully."""
        logger.info("Shutdown signal received, terminating services...")
        for p in procs:
            if p.poll() is None:
                p.terminate()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.only in ("stt", "both"):
            procs.append(start_service("stt.server:app", args.stt_host, args.stt_port))

        if args.only in ("tts", "both"):
            procs.append(start_service("tts.server:app", args.tts_host, args.tts_port))

        # Wait for all processes to complete
        for p in procs:
            p.wait()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        for p in procs:
            if p.poll() is None:
                logger.info(f"Terminating process {p.pid}...")
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Process {p.pid} did not exit, killing forcefully")
                    p.kill()
                    p.wait()

        logger.info("All services stopped")

    return 0


if __name__ == "__main__":
    sys.exit(main())
