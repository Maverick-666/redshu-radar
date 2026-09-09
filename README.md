# 红薯雷达

运行在 macOS 本地的小红书虚拟资料选品监控工具。

它用公开商品详情接口建立可信销量快照，以 20–28 小时窗口计算 24 小时增量。采集失败不会被写成销量 0，错过每日锚点只会形成跨期数据，不会伪造缺失快照。

## 首次启动

需要 macOS、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Python 3.12。进入项目目录后运行：

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv sync --group dev
uv run redshu-radar web
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)，点击“添加商品”，可逐行粘贴分享文案、完整商品链接、短链或 24 位商品 ID。首次导入会立即建立基线；至少再获得一次相隔 20–28 小时的可信快照后，商品才进入完整 24 小时榜单。

停止看板：回到终端按 `Control-C`。

## 每日自动采集

确认手动启动和采集正常后，可安装每日 00:02 的用户级调度：

```bash
./scripts/install-launch-agent.sh
launchctl print gui/$(id -u)/com.maverick.redshu-radar.daily
```

调度只在一次采集进程运行时使用 `/usr/bin/caffeinate -i` 防止空闲休眠，不修改全局睡眠设置；合盖仍会正常休眠。Mac 与网络无需 24 小时在线，只需尽量在 00:02 附近醒着联网。错过后，下一次启动看板会尝试恢复采集。

手动采集和卸载调度：

```bash
uv run redshu-radar collect --trigger manual
./scripts/uninstall-launch-agent.sh
```

卸载调度不会删除数据库。

## 数据位置与验证

默认数据库：`~/Library/Application Support/RedshuRadar/redshu-radar.sqlite3`。商品、快照、采集尝试和人工判断只保存在本机；v0 不需要小红书账号 Cookie。

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv run pytest -q
uv run redshu-radar --version
```

项目固定使用 Python 3.12，不使用 macOS 自带的 Python 3.9。这里显式使用非隐藏的 `venv` 目录，避免当前 macOS 将默认 `.venv` 内的 editable 路径标记为隐藏。

睡眠、断网、备份、恢复、换机和故障检查见 [本地运行手册](docs/operations/local-runbook.md)。
