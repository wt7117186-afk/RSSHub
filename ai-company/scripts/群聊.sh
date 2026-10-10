#!/usr/bin/env bash
# Telegram 工作群命令的简写。用法：./scripts/群聊.sh 看 | 等 [秒] | 说 <文本> | 历史 [条数] | run | ids
exec python3 "$(dirname "$0")/../telegram/hub.py" "$@"
