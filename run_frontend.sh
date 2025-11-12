#!/bin/bash
# Script to run the frontend
cd "$(dirname "$0")"
uv run streamlit run frontend/app.py

