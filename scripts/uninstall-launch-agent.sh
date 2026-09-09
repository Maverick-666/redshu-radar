#!/bin/zsh
set -euo pipefail

TARGET="${HOME}/Library/LaunchAgents/com.maverick.redshu-radar.daily.plist"
DOMAIN="gui/$(id -u)"

launchctl bootout "${DOMAIN}" "${TARGET}" 2>/dev/null || true
rm -f "${TARGET}"

print "已卸载定时任务；本地业务数据保持不变。"
