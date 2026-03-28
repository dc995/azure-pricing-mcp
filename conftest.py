"""Pytest configuration — prevent __init__.py relative import issues."""
import sys
from pathlib import Path

# Ensure the project root is on sys.path so modules import directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

collect_ignore = ["__init__.py", "__main__.py", "setup.py"]
