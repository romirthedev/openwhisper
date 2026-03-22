"""
py2app build configuration.

Usage:
    pip install py2app
    python setup.py py2app

The resulting .app will be in dist/OpenWhisper.app
"""
from setuptools import setup

APP = ["run.py"]
DATA_FILES = []

OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,          # Set to "assets/icon.icns" if you add an icon
    "plist": {
        "CFBundleName": "OpenWhisper",
        "CFBundleDisplayName": "OpenWhisper",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        # Run as a regular app (shows in Dock)
        "LSUIElement": False,
        # Required permission descriptions (shown to user by macOS)
        "NSMicrophoneUsageDescription":
            "OpenWhisper needs microphone access to record your voice.",
        "NSAppleEventsUsageDescription":
            "OpenWhisper needs Accessibility access to type transcribed text.",
    },
    "packages": [
        "customtkinter",
        "faster_whisper",
        "sounddevice",
        "numpy",
        "pynput",
        "pyperclip",
        "requests",
        "sqlite3",
    ],
    "includes": [
        "tkinter",
        "tkinter.ttk",
        "_tkinter",
        "queue",
        "threading",
        "pathlib",
        "json",
        "re",
        "time",
        "datetime",
    ],
    "excludes": ["matplotlib", "scipy", "pandas"],
}

setup(
    name="OpenWhisper",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
