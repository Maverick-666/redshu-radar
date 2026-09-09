# 红薯雷达 v0 实施计划

- 日期：2026-09-09
- 对应规格：[`../specs/2026-09-09-redshu-radar-mac-design.md`](../specs/2026-09-09-redshu-radar-mac-design.md)
- 目标环境：Apple Silicon Mac，Python 3.12.13，`uv`
- 计划状态：待用户复核；尚未开始实现

## 1. 完成定义

v0 只有在以下证据同时存在时才完成：

1. 本地 Web 看板可添加、查看和筛选真实商品。
2. 第一批 10–20 个商品完成首次基线和连续两个可信日级锚点。
3. 断网、失败响应和销量回退不会生成假 0 或污染可信高水位。
4. 每个 24 小时指标都可追溯到两个实际快照。
5. `launchd` 能在每日 00:02 调用采集命令，采集期间临时防止空闲休眠。
6. 用户据此选出至少 1 个商品进入人工复核或测试。

业务目标仍是 9 月真实发布、反馈、成交和 3000 元利润，不能用“软件写完”替代。

## 2. 技术栈与目录

采用最小的服务端渲染 Web 栈，不引入前端构建系统：

- Python 3.12，由 `uv` 固定和管理。
- FastAPI + Uvicorn：本地 HTTP 服务和 JSON API。
- Jinja2 + 原生 CSS/JavaScript：桌面看板。
- Python `sqlite3` + WAL：唯一事实源。
- Python 标准库 `urllib`：公开接口主采集通道。
- 系统 `curl`：第二层直接请求兜底。
- Pytest：规则、数据库、接口与集成测试。

```text
redshu-radar/
├── pyproject.toml
├── README.md
├── src/redshu_radar/
│   ├── cli.py
│   ├── config.py
│   ├── domain.py
│   ├── parsing/
│   ├── collectors/
│   ├── storage/
│   ├── analytics/
│   ├── services/
│   └── web/
│       ├── app.py
│       ├── templates/
│       └── static/
├── migrations/
├── launchd/
├── scripts/
├── tests/
│   └── fixtures/
└── docs/
```

系统自带 Python 3.9.6 不参与运行或测试。

## 3. 实施原则

- 每个行为先写失败测试，再写最少实现，再运行相关测试和全量测试。
- 每项任务单独提交，避免把采集、统计和页面揉在一次大改中。
- 所有外部响应先进入校验层；页面和统计代码禁止直接解析原始 JSON。
- 错误记录与销量快照分表，数据库约束阻止失败写成销量。
- 实时接口只用于烟雾验证；自动测试使用脱敏固定样本。
- v0 不安装或复制 `Spider_XHS`，不实现账号自动化和内容批量发布。

## 4. 任务拆解

### 任务 1：建立可运行、可测试的项目骨架

新增：

- `pyproject.toml`
- `.gitignore`
- `README.md`
- `src/redshu_radar/__init__.py`
- `src/redshu_radar/cli.py`
- `src/redshu_radar/config.py`
- `tests/test_smoke.py`

步骤：

1. 写一个导入包和读取临时配置目录的失败测试。
2. 用 `uv` 固定 Python 3.12，加入运行与测试依赖。
3. 实现最小配置对象：数据库路径、日志路径、主机和端口。
4. 运行 `uv run pytest tests/test_smoke.py -q`。
5. 运行 `uv run pytest -q`。

验收：全新检出后可按 README 创建环境并运行测试；数据库默认进入用户数据目录，不进入 Git。

提交：`chore: scaffold redshu radar application`

### 任务 2：定义领域对象与 SQLite 唯一事实源

新增：

- `src/redshu_radar/domain.py`
- `src/redshu_radar/storage/database.py`
- `src/redshu_radar/storage/repositories.py`
- `migrations/001_initial.sql`
- `tests/storage/test_database.py`
- `tests/storage/test_repositories.py`

步骤：

1. 为 `products`、`collection_runs`、`collection_attempts`、`snapshots` 写建表和约束测试。
2. 验证数据库启动时启用 WAL 和外键。
3. 验证同一商品不会重复创建，可信快照可按时间查询。
4. 验证失败尝试只能进入 `collection_attempts`，不能生成 `snapshots`。
5. 实现最小迁移与仓储代码。
6. 运行 storage 测试和全量测试。

验收：临时数据库重启后数据保持一致；重复写入行为明确且幂等。

提交：`feat: add sqlite source of truth`

### 任务 3：实现四类商品输入解析

新增：

- `src/redshu_radar/parsing/item_input.py`
- `src/redshu_radar/parsing/short_links.py`
- `tests/parsing/test_item_input.py`
- `tests/parsing/test_short_links.py`

步骤：

1. 为 24 位 ID、完整商品 URL、含 URL 的分享文案和批量多行输入写测试。
2. 为非法文本、多链接歧义、重复 ID 和空行写测试。
3. 为 `xhslink.com` 有限重定向写可注入传输层的测试，不访问真实网络。
4. 实现纯解析函数和短链解析器。
5. 运行 parsing 测试和全量测试。

验收：每行输入都返回成功 ID 或明确错误，任何单行失败不影响其他行。

提交：`feat: parse xhs product inputs`

### 任务 4：实现公开接口响应校验与字段标准化

新增：

- `src/redshu_radar/collectors/models.py`
- `src/redshu_radar/collectors/response_parser.py`
- `tests/collectors/test_response_parser.py`
- `tests/fixtures/product_success.json`
- `tests/fixtures/product_zero_sales.json`
- `tests/fixtures/product_business_error.json`
- `tests/fixtures/product_missing_fields.json`

步骤：

1. 从真实响应制作脱敏样本，只保留结构和测试所需字段。
2. 为标题、店铺、价格、`123 / 1.2万 / 1.2w` 累计销量写解析测试。
3. 为 `success=false`、缺失 `template_data`、缺价格和不可解析销量写失败测试。
4. 明确测试：完整成功响应中的空销量才可得到 0；网络或结构错误永远不得得到 0。
5. 实现集中式字段路径和标准化对象。
6. 运行 collector parser 测试和全量测试。

验收：页面、数据库和统计层只接收标准化对象，不接触原始字段路径。

提交：`feat: validate xhs product responses`

### 任务 5：实现直接采集、重试和错误分类

新增：

- `src/redshu_radar/collectors/base.py`
- `src/redshu_radar/collectors/public_api.py`
- `src/redshu_radar/collectors/transports.py`
- `src/redshu_radar/services/collection_service.py`
- `tests/collectors/test_public_api.py`
- `tests/services/test_collection_service.py`

步骤：

1. 定义采集适配器协议和统一错误：超时、网络、HTTP 461、业务失败、结构变化、疑似下架。
2. 测试 `urllib` 成功和失败后切到系统 `curl` 的行为。
3. 测试有限重试、461 冷却、单品失败不终止批次。
4. 测试成功写快照、失败只写尝试记录。
5. 测试报告销量回退时保留原始报告值，统计侧仍使用可信高水位。
6. 实现批次服务和运行摘要。
7. 运行相关测试和全量测试。

验收：任何失败路径都不能调用“保存可信快照”的仓储方法。

提交：`feat: collect trusted product snapshots`

### 任务 6：实现统一统计与数据质量状态

新增：

- `src/redshu_radar/analytics/windows.py`
- `src/redshu_radar/analytics/metrics.py`
- `src/redshu_radar/analytics/ranking.py`
- `tests/analytics/test_windows.py`
- `tests/analytics/test_metrics.py`
- `tests/analytics/test_ranking.py`

步骤：

1. 为 20、24、28 小时时间边界及边界外样本写测试。
2. 为首次采集、缺基线、跨 48 小时、小时缺失和销量回退写状态测试。
3. 为 24 小时增量、爆品值和商品价值写精确算例。
4. 测试跨期样本只返回总增量和日均参考，不进入主榜。
5. 测试排序稳定性、除零和价格缺失。
6. 实现纯统计函数与榜单查询服务。
7. 运行 analytics 测试和全量测试。

验收：任一榜单值都附带起止快照时间和数据质量状态。

提交：`feat: calculate trusted radar metrics`

### 任务 7：实现应用服务与本地 API

新增：

- `src/redshu_radar/services/product_service.py`
- `src/redshu_radar/services/radar_service.py`
- `src/redshu_radar/web/app.py`
- `src/redshu_radar/web/schemas.py`
- `tests/web/test_api.py`

最小接口：

- `GET /api/status`
- `GET /api/products`
- `POST /api/products/import`
- `GET /api/products/{item_id}`
- `PATCH /api/products/{item_id}/decision`
- `POST /api/collections`

步骤：

1. 先写 API 成功、验证失败和部分批次失败测试。
2. 确保 API 只编排服务，不重复指标公式。
3. 暴露运行状态、数据库体积、快照数和最近采集时间。
4. 运行 web API 测试和全量测试。

验收：相同统计服务未来可直接供只读 MCP 和通知调用。

提交：`feat: expose local radar api`

### 任务 8：实现主榜单与两个抽屉

新增：

- `src/redshu_radar/web/templates/index.html`
- `src/redshu_radar/web/static/styles.css`
- `src/redshu_radar/web/static/app.js`
- `tests/web/test_pages.py`

实现重点：

- 参考群友“红薯台”的浅灰、白卡片、绿色操作和高密度表格语言。
- 顶部始终可见运行状态、数据库体积和快照数。
- 完整日级、待基线、跨期、异常分别筛选。
- 表格列严格使用共享统计服务结果。
- 批量添加抽屉逐行返回成功、重复和失败。
- 商品详情抽屉展示快照、数据解释和四类人工字段。
- 所有浅色背景使用高对比深色文字。

步骤：

1. 写页面结构、关键文案和静态资源测试。
2. 完成无前端框架的最小交互。
3. 用窄窗口和桌面宽屏人工检查，不追求移动端完整适配。
4. 运行 web 测试和全量测试。

验收：用户不进入日志即可判断系统是否运行、数据是否完整以及下一步该看哪个商品。

提交：`feat: build local radar dashboard`

### 任务 9：实现 CLI、日级调度与临时防空闲休眠

新增：

- `launchd/com.maverick.redshu-radar.daily.plist.template`
- `scripts/install-launch-agent.sh`
- `scripts/uninstall-launch-agent.sh`
- `tests/test_cli.py`
- `tests/test_launchd_config.py`

步骤：

1. 为 `collect --trigger daily|hourly|manual|recovery` 写 CLI 测试。
2. 为“锚点逾期后补采”和“跨期不入榜”写服务测试。
3. 生成每日 00:02 的 `launchd` 配置，安装时写入项目与 `uv` 的绝对路径。
4. 让调度命令通过 `/usr/bin/caffeinate -i` 包裹采集进程，只在该进程期间阻止空闲休眠。
5. 写安装、查看状态、卸载和手动触发说明。
6. 验证脚本幂等，卸载不会删除数据库。
7. 运行 CLI、调度配置和全量测试。

验收：不修改系统全局睡眠设置；合盖仍正常休眠；醒来后可补采真实快照。

提交：`feat: schedule mac daily collection`

### 任务 10：端到端验证与运行手册

修改或新增：

- `README.md`
- `docs/operations/local-runbook.md`
- `tests/integration/test_end_to_end.py`

步骤：

1. 用脱敏 fixture 跑“导入 → 采集 → 快照 → 统计 → API → 页面”集成测试。
2. 用一个公开商品执行可选实时烟雾测试，明确不把结果写进测试仓库。
3. 人工断网一次，确认失败记录存在且快照数不增加。
4. 人工构造跨期和回退数据，确认状态、榜单和解释一致。
5. 启动本地看板，核对参考图中的状态条、表格层级和操作位置。
6. 补齐启动、停止、备份数据库、恢复和卸载调度的说明。
7. 运行 `uv run pytest -q`，并记录测试数量与结果。

验收：新用户只看 README 即可启动；运行手册覆盖睡眠、断网、迁移和备份。

提交：`docs: add local operations and acceptance guide`

### 任务 11：首批真实商品验收

此任务需要用户提供或当场加入真实候选，不用测试数据冒充。

步骤：

1. 添加 10–20 个真实商品并核对标题、店铺、价格和累计已售。
2. 保持每日 23:50–00:05 醒着联网，获得连续两个可信锚点。
3. 查看主榜、跨期和异常过滤，随机抽查指标对应的起止快照。
4. 选出至少 1 个商品，填写人群—场景—问题—交付和下一步。
5. 记录人工测试结果；未得到真实发布或测试动作时，不宣布业务闭环完成。

验收：满足设计规格第 14 节全部五项。

提交：只提交脱敏后的验收记录，不提交商品账号凭证、Cookie 或敏感数据。

## 5. 与首周账号准备并行的非代码工作

这条线由用户人工完成，程序不模拟用户行为：

- 第 1–2 天：确定首个细分选品方向、关键词和 10 个同行账号。
- 第 3–4 天：观察标题、封面、正文、评论需求和交付承诺，记录模式而非复制内容。
- 第 5–6 天：把对应商品加入雷达，形成候选池；筛掉交付难、侵权或需求含糊的方向。
- 第 7 天：形成 1–3 个原创测试方案，准备首轮发布。

这使“账号准备的一周”和“开发的一周”并行，而不是先后等待。

## 6. 后期内容情报模块的前置约束

`Spider_XHS` 当前只作为能力参考：

- 不加入依赖、不复制代码、不接入商业流程。
- 复用前必须重新核验许可证并获得必要授权。
- 首选只读的关键词、笔记详情和评论研究，不从自动发布起步。
- Cookie、登录态和账号数据必须进入本机密钥或私有数据目录，永不提交 Git。
- 内容情报使用独立表和采集适配器，只通过主题或商品 ID 与销量雷达关联。
- 自动化必须有速率限制、人工开关、可追溯来源和明确停止条件。

## 7. 明确延后

- Playwright 浏览器兜底。
- 自动拓品、店铺分析和多账号管理。
- 企业微信通知和只读 MCP。
- 同行笔记批量采集。
- AI 改写、自动发布、私信和评论自动化。
- Mac `.app`、DMG 和远程常驻部署。

只有 v0 的真实运行证据说明某项延后能力已成为瓶颈，才为它开启新的设计与实现周期。
