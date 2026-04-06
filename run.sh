#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
exec -a mint-wallpaper-studio python3 main.py "$@"
