# 红薯雷达本地运行手册

## 1. 运行模型

红薯雷达由三部分组成：本地 Web 看板、SQLite 数据库、每日 00:02 的可选 `launchd` 任务。SQLite 是唯一事实源；页面指标都从可信快照计算。

默认位置：

- 项目：本仓库所在目录
- 数据目录：`~/Library/Application Support/RedshuRadar`
- 数据库：`~/Library/Application Support/RedshuRadar/redshu-radar.sqlite3`
- 调度日志：同一数据目录下的 `collector.stdout.log` 和 `collector.stderr.log`
- LaunchAgent：`~/Library/LaunchAgents/com.maverick.redshu-radar.daily.plist`

项目移动到新目录后需要重新安装 LaunchAgent，因为 plist 中保存项目与 Python 环境的绝对路径。

## 2. 启动、停止与手动采集

每个新终端先进入项目并指定非隐藏虚拟环境：

```bash
cd /path/to/redshu-radar
export UV_PROJECT_ENVIRONMENT=venv
```

启动看板：

```bash
uv run redshu-radar web
```

浏览器打开 `http://127.0.0.1:8765`。终端按 `Control-C` 停止。看板只监听本机地址，不对局域网或公网开放。

手动采集：

```bash
uv run redshu-radar collect --trigger manual
```

程序输出本次运行 ID、成功数、失败数和总体状态。`partial` 表示同一批次有成功也有失败；单个商品失败不会中断其他商品。

## 3. 每日调度

安装或重新安装：

```bash
./scripts/install-launch-agent.sh
```

脚本可重复运行；它会先卸载旧配置，再写入并加载当前项目路径。查看状态：

```bash
launchctl print gui/$(id -u)/com.maverick.redshu-radar.daily
```

查看最近日志：

```bash
tail -n 100 "$HOME/Library/Application Support/RedshuRadar/collector.stdout.log"
tail -n 100 "$HOME/Library/Application Support/RedshuRadar/collector.stderr.log"
```

手动验证与调度相同的运行链路：

```bash
/usr/bin/caffeinate -i venv/bin/python -m redshu_radar.cli collect --trigger daily
```

卸载：

```bash
./scripts/uninstall-launch-agent.sh
```

卸载只移除 LaunchAgent，不删除数据库、日志或项目。

## 4. 睡眠、合盖、断网和坐飞机

- 不需要 24 小时开机，也不需要持续联网。网络只在一次采集请求期间使用。
- 正常目标是让 Mac 在 23:50–00:05 醒着、用户已登录且网络可用，调度会在 00:02 运行。
- `/usr/bin/caffeinate -i` 只在采集进程运行期间阻止空闲休眠；进程退出后自动释放。它不会阻止合盖休眠，也不会修改 `pmset`。
- 合盖、关机、飞行模式或坐飞机只会让本次锚点缺失，不会损坏已有数据。再次启动看板时，若完整成功采集已逾期，会以 `recovery` 补采真实快照。
- 相邻可信快照相隔 20–28 小时才进入完整 24 小时榜单。超过 28 小时只显示实际总增量和折算日均，状态为“跨期 · 不入榜”。获得新的干净日级窗口后自动恢复。
- 断网、DNS、超时、HTTP 461、业务失败或接口结构变化只记录失败尝试，不新增快照，也不会把未知销量写成 0。

因此，不可抗力通常影响的是一两天的数据完整性，不是历史安全。若连续多天无法采集，先看顶部运行状态和调度错误日志，再用手动采集验证网络与公开接口。

## 5. 常见状态

- `完整 24h`：存在 20–28 小时的可信基线，可进入主榜。
- `待基线`：只有首次快照，等待下一次日级采集。
- `时段数据`：已有增量，但间隔不足 20 小时，仅作参考。
- `跨期 · 不入榜`：间隔超过 28 小时，不冒充完整 24 小时数据。
- `销量回退`：接口报告值低于历史可信高水位；保留原始快照但不计算负销量。
- 顶部“部分失败/失败”：查看调度日志；可信快照总数不应因失败而增加。

爆品值和商品价值只是“先看谁”的排序信号，不等于利润。最终仍需人工检查人群、场景、问题、交付、内容、版权合规和成本。

## 6. 备份

SQLite 处于 WAL 模式。推荐用 SQLite 自带的在线备份命令获得一致副本，无需直接复制三个 WAL 文件：

```bash
mkdir -p "$HOME/Documents/RedshuRadar-Backups"
backup_path="$HOME/Documents/RedshuRadar-Backups/redshu-radar-$(date +%F-%H%M%S).sqlite3"
sqlite3 "$HOME/Library/Application Support/RedshuRadar/redshu-radar.sqlite3" ".backup '$backup_path'"
echo "$backup_path"
```

建议在首次真实候选导入后、重要人工判断后和换机前各备份一次。备份包含商品、快照、运行历史与人工字段，不包含程序代码。

## 7. 恢复

恢复会覆盖当前数据库。先停止看板并卸载调度，然后保留当前副本：

```bash
./scripts/uninstall-launch-agent.sh
data_dir="$HOME/Library/Application Support/RedshuRadar"
cp "$data_dir/redshu-radar.sqlite3" "$data_dir/redshu-radar.before-restore.sqlite3"
sqlite3 "$data_dir/redshu-radar.sqlite3" ".restore '/替换为备份文件的绝对路径.sqlite3'"
```

重新启动看板核对商品数、快照数和人工字段；确认后再重新安装调度。若恢复失败，停止应用后可用保留的 `redshu-radar.before-restore.sqlite3` 回退。

## 8. 换目录或换 Mac

1. 在旧机器按第 6 节生成单文件备份。
2. 在新目录取得项目，安装 uv，并运行 `UV_PROJECT_ENVIRONMENT=venv uv sync --group dev`。
3. 新机器创建 `~/Library/Application Support/RedshuRadar`，把备份放为 `redshu-radar.sqlite3`。
4. 运行 `UV_PROJECT_ENVIRONMENT=venv uv run pytest -q`，再启动看板核对数据。
5. 在新项目目录重新运行 `./scripts/install-launch-agent.sh`，使绝对路径生效。

不要迁移或提交 Cookie、浏览器登录态或账号凭证；v0 不需要这些内容。

## 9. 故障检查顺序

1. 看页面顶部：运行状态、可信快照数、数据库体积是否合理。
2. 手动运行 `UV_PROJECT_ENVIRONMENT=venv uv run redshu-radar collect --trigger manual`。
3. 若失败，查看终端摘要及 `collector.stderr.log`；HTTP 461 时不要连续追打。
4. 运行 `launchctl print gui/$(id -u)/com.maverick.redshu-radar.daily` 确认调度已加载。
5. 若公开接口字段变化，停止自动采集并修复集中解析器；不要把空字段当作销量 0。
6. 数据异常时先备份，再运行 `sqlite3 "$HOME/Library/Application Support/RedshuRadar/redshu-radar.sqlite3" "PRAGMA integrity_check;"`。

公开接口属于外部依赖，可能变化或触发频控。v0 的安全策略是明确失败并保留上一份可信数据，而不是保证每次请求都成功。
