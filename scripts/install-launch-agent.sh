#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="${SCRIPT_DIR:h}"
DATA_DIR="${HOME}/Library/Application Support/RedshuRadar"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET="${TARGET_DIR}/com.maverick.redshu-radar.daily.plist"
TEMPLATE="${PROJECT_DIR}/launchd/com.maverick.redshu-radar.daily.plist.template"
DOMAIN="gui/$(id -u)"

if [[ ! -x "${PROJECT_DIR}/venv/bin/python" ]]; then
  print -u2 "缺少 venv。请先按 README 完成 uv sync。"
  exit 1
fi

mkdir -p "${DATA_DIR}" "${TARGET_DIR}"
sed -e "s|__PROJECT_DIR__|${PROJECT_DIR}|g" -e "s|__DATA_DIR__|${DATA_DIR}|g" "${TEMPLATE}" > "${TARGET}"

launchctl bootout "${DOMAIN}" "${TARGET}" 2>/dev/null || true
launchctl bootstrap "${DOMAIN}" "${TARGET}"
launchctl enable "${DOMAIN}/com.maverick.redshu-radar.daily"

print "已安装：${TARGET}"
print "每日 00:02 采集；数据库保存在：${DATA_DIR}"
