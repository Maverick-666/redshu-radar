# 红薯雷达分类与监控基础实施计划

- 日期：2026-09-10
- 对应规格：[`../specs/2026-09-10-classification-foundation-design.md`](../specs/2026-09-10-classification-foundation-design.md)
- 分支：`feature/classification-foundation`
- 计划状态：已获用户继续授权

## 1. 完成定义

只有以下证据同时存在，本阶段才算完成：

1. 现有数据库可无损增加两级分类、多标签和商品分类关联。
2. 当前 16 个商品仍保持原有监控状态，37 条现有快照不变。
3. 商品详情可保存分类、标签、监控状态和原有人工判断。
4. 搜索与筛选可组合匹配商品、店铺、ID、赛道、细分品类和标签。
5. 多标签使用 AND 语义；筛选后继续使用既有数值排序。
6. 页面筛选入口保持紧凑，每行最多展示两个标签和“+N”。
7. 停用商品不进入采集，重新启用不生成假快照。
8. 全量自动测试、JavaScript 语法检查、迁移前后数据核对和浏览器烟雾测试通过。

## 2. 实施原则

- 每项行为先写失败测试，再写最少实现。
- 不改采集响应解析、快照结构或销量指标公式。
- 使用现有 `enabled`，不新建重复监控状态。
- 数据库迁移只增加结构，不回填未经用户确认的分类。
- 不实现店铺分析、笔记研究、账号凭证或自动分类。
- 每个任务独立提交，最终复审通过后再合并 `main`。

## 3. 任务拆解

### 任务 1：增加可重复执行的分类数据迁移

修改或新增：

- `migrations/002_taxonomy.sql`
- `src/redshu_radar/storage/database.py`
- `src/redshu_radar/domain.py`
- `tests/storage/test_database.py`

步骤：

1. 写失败测试：旧版临时数据库含商品和快照，升级后原数据及计数不变。
2. 写失败测试：重复调用 `initialize()` 不重复字段、表或数据。
3. 写失败测试：分类、标签和关联表启用外键、唯一索引和两级结构所需字段。
4. 实现增量迁移：先创建分类表，再通过 `PRAGMA table_info(products)` 判断并增加 `category_id`。
5. 更新领域对象，使商品可携带可空分类 ID，不改变现有默认行为。
6. 运行：`venv/bin/pytest tests/storage/test_database.py -q -p no:cacheprovider`。
7. 运行全量测试。

验收：旧数据无损，初始化幂等，未分类商品正常读取。

提交：`feat: add taxonomy database migration`

### 任务 2：实现分类仓储与规则服务

修改或新增：

- `src/redshu_radar/domain.py`
- `src/redshu_radar/storage/repositories.py`
- `src/redshu_radar/services/taxonomy_service.py`
- `tests/storage/test_repositories.py`
- `tests/services/test_taxonomy_service.py`

步骤：

1. 写失败测试：创建赛道和细分品类、同级规范化名称去重。
2. 写失败测试：拒绝把细分品类继续作为父级，拒绝商品关联赛道。
3. 写失败测试：标签去空白、合并空白、英文大小写去重。
4. 写失败测试：商品标签可替换、清空，重复关联保持幂等。
5. 实现 `CategoryRepository`、`TagRepository` 和最小 `TaxonomyService`。
6. 所有商品分类与标签更新使用同一数据库事务入口。
7. 运行仓储、服务和全量测试。

验收：层级、去重和关联语义集中在服务/仓储，不散落到页面。

提交：`feat: add taxonomy repositories and service`

### 任务 3：扩展商品更新与本地 API

修改：

- `src/redshu_radar/storage/repositories.py`
- `src/redshu_radar/services/radar_service.py`
- `src/redshu_radar/web/schemas.py`
- `src/redshu_radar/web/app.py`
- `tests/web/test_api.py`
- `tests/services/test_collection_service.py`

步骤：

1. 写失败测试：商品列表和详情返回赛道、细分品类、标签及 `enabled`。
2. 写失败测试：读取和创建分类、标签接口正确去重和验证父级。
3. 写失败测试：详情更新可原子保存分类、标签、`enabled` 和既有人工字段。
4. 写失败测试：不存在或层级错误的分类/标签返回明确 4xx，原记录不变。
5. 写失败测试：`enabled=0` 商品不进入全量采集，重新启用后等待真实快照。
6. 实现最小 API 和服务编排，不在路由中复制规则。
7. 运行 API、采集服务和全量测试。

验收：API 是页面唯一写入口；错误不会留下半保存状态。

提交：`feat: expose product taxonomy api`

### 任务 4：实现紧凑分类筛选与详情编辑

修改：

- `src/redshu_radar/web/templates/index.html`
- `src/redshu_radar/web/static/styles.css`
- `src/redshu_radar/web/static/app.js`
- `tests/web/test_pages.py`

步骤：

1. 写失败页面测试：存在赛道、细分品类、标签和监控筛选入口，以及详情编辑控件。
2. 扩展前端状态：赛道单选、细分品类单选、标签多选、监控状态。
3. 搜索字段增加赛道、细分品类和标签；多标签使用 AND。
4. 保证处理顺序为搜索/筛选 → 既有数值排序。
5. 列表每行最多渲染两个标签，剩余显示“+N”。
6. 筛选工具只显示固定入口和激活计数，不为每个值永久增加按钮。
7. 详情保存失败时保留输入并显示错误；成功后重新渲染当前筛选结果。
8. 运行页面测试、`node --check` 和全量测试。

验收：分类调整后可立即检索；筛选入口不会随标签数量横向膨胀。

提交：`feat: add compact taxonomy workflow`

### 任务 5：真实数据库迁移与端到端验收

修改：

- `README.md`
- 必要的集成测试文件

步骤：

1. 停止本地 Web 服务，确认没有采集任务正在运行。
2. 为正式 SQLite 文件创建带时间戳的只读备份副本。
3. 记录迁移前商品数、快照数、采集运行数和各商品 `enabled`。
4. 用新版本初始化正式数据库并记录迁移后相同指标。
5. 验证 16 个商品仍启用、37 条当前快照不变、分类为空。
6. 启动本地 Web 页面，人工完成：创建赛道/细分品类/标签、关联一个商品、搜索、组合筛选、排序、候选/监控切换。
7. 恢复测试商品的监控状态，不触发额外手动采集，避免污染今晚基线。
8. 更新 README 的分类流程、数据位置和恢复说明。
9. 运行全量测试、JavaScript 语法检查和 `git diff --check`。

验收：正式数据无损；页面闭环可用；每日 `00:02` 调度保持已注册状态。

提交：`docs: document taxonomy workflow`

## 4. 复审与集成

1. 对规格逐条核验实现和测试。
2. 请求独立代码复审，修复所有 Critical 和 Important 问题。
3. 在功能分支重新运行全量验证。
4. 快进合并回本地 `main`。
5. 在 `main` 再次运行全量验证。
6. 推送公开 GitHub 仓库并删除已合并的本地功能分支。

## 5. 风险控制

- 正式数据库迁移前必须备份，且不得在每日 `00:02` 采集窗口执行迁移。
- 自动测试只使用临时数据库；不得将正式商品或快照写入测试夹具。
- 浏览器验收不触发“立即采集”。
- 若迁移前后计数或 `enabled` 状态不一致，立即停止，不继续页面验收或合并。
- 若新增筛选需要改变现有销量口径，视为设计冲突并停止实现。
