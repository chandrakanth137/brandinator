#!/bin/bash
# Script to run the backend server
cd "$(dirname "$0")"
uv run backend/app/main.py

