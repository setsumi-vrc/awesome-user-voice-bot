#!/usr/bin/env python3
"""
Test runner script for TTS Server
"""
import subprocess
import sys
from pathlib import Path

def run_tests():
    """Run all unit tests."""
    venv_python = Path(__file__).parent / "venv" / "Scripts" / "python.exe"

    if not venv_python.exists():
        print("Virtual environment not found. Please run setup first.")
        return 1

    # Run pytest
    cmd = [str(venv_python), "-m", "pytest"]
    result = subprocess.run(cmd, cwd=Path(__file__).parent)

    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())