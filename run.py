#!/usr/bin/env python3
"""
OpenWhisper – entry point.

Usage:
    python run.py

Requirements: see requirements.txt
"""
import sys
import os

# Put src/ on the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from main import OpenWhisperApp
from ui.app import MainWindow


def main():
    core = OpenWhisperApp()
    window = MainWindow(core)
    window.run()


if __name__ == "__main__":
    main()
