#!/usr/bin/env bash
printf '\033c'
cd "$(dirname "$(readlink -f "$0")")" && exec python3 ai_remote.py
