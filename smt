#!/usr/bin/env python3
"""Repository-local isolated launcher."""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(ROOT, "smt_coach.py")
os.execv(sys.executable, [sys.executable, "-I", "-S", "-B", TARGET, *sys.argv[1:]])
