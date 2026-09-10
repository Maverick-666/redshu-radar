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

## 分类、筛选与监控

- 在商品详情中选择是否监控，并维护“赛道 → 细分品类”和多个标签；赛道与细分品类只支持两级，商品关联到细分品类。
- “＋赛道 / ＋细分 / ＋标签”共用一个创建窗口，不会随着分类数量增加而堆积按钮。
- 搜索会匹配商品名、店铺、商品 ID、赛道、细分品类和标签；多个标签使用 AND 语义，即商品必须同时具备所有已选标签。
- 搜索和筛选先执行，再使用表头上的价格、销量、增量、爆品值或商品价值排序。列表每行最多显示两个标签，其余折叠为“+N”。
- 关闭监控后商品不会进入后续采集；重新开启只等待新的真实快照，不补写销量 0，也不会伪造基线。

首次使用建议先建立少量稳定赛道和细分品类，再为候选商品补标签。分类和标签都保存在本地 SQLite 中，不会上传账号凭证。

## 每日自动采集

确认手动启动和采集正常后，可安装每日 00:02 的用户级调度：

```bash
./scripts/install-launch-agent.sh
launchctl print gui/$(id -u)/com.maverick.redshu-radar.daily
```

调度只在一次采集进程运行时使用 `/usr/bin/caffeinate -i` 防止空闲休眠，不修改全局睡眠设置；合盖仍会正常休眠。Mac 与网络无需 24 小时在线，只需尽量在 00:02 附近醒着联网。错过后，下一次启动看板会尝试恢复采集。

`launchd` 会直接运行当前项目目录中的代码。若项目升级包含数据库迁移，下一次 Web 启动、手动采集或自动采集都可能先执行迁移；因此升级前应先按下方说明备份数据库。迁移只增加结构，不会替用户自动填写分类。

手动采集和卸载调度：

```bash
uv run redshu-radar collect --trigger manual
./scripts/uninstall-launch-agent.sh
```

卸载调度不会删除数据库。

## 数据位置与验证

默认数据库：`~/Library/Application Support/RedshuRadar/redshu-radar.sqlite3`。商品、快照、采集尝试和人工判断只保存在本机；v0 不需要小红书账号 Cookie。

创建一致性备份（SQLite 使用 WAL 模式，不建议只复制主文件）：

```bash
mkdir -p "$HOME/Documents/RedshuRadar-Backups"
backup_path="$HOME/Documents/RedshuRadar-Backups/redshu-radar-$(date +%F-%H%M%S).sqlite3"
sqlite3 "$HOME/Library/Application Support/RedshuRadar/redshu-radar.sqlite3" ".backup '$backup_path'"
sqlite3 "$backup_path" "PRAGMA integrity_check;"
```

恢复会覆盖当前数据。先停止看板并卸载调度，再按照[本地运行手册](docs/operations/local-runbook.md)的恢复步骤操作；不要在 `00:02` 采集窗口附近恢复或迁移。

```bash
export UV_PROJECT_ENVIRONMENT=venv
uv run pytest -q
uv run redshu-radar --version
```

项目固定使用 Python 3.12，不使用 macOS 自带的 Python 3.9。这里显式使用非隐藏的 `venv` 目录，避免当前 macOS 将默认 `.venv` 内的 editable 路径标记为隐藏。

睡眠、断网、备份、恢复、换机和故障检查见 [本地运行手册](docs/operations/local-runbook.md)。
