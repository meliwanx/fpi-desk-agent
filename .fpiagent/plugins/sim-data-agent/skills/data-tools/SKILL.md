---
name: data-tools
description: Use SIM data warehouse tools from the desktop agent for tenant 3 schema discovery, lineage, semantic lookup, read-only PGSQL querying, CSV export, and SQL draft generation.
---

# SIM 数据中台工具

当用户询问公司数据、数仓表结构、PGSQL 查询、血缘、语义指标、业务术语、字段值定位、SQL 草稿或 CSV 导出时，优先使用本技能。

## 范围

- 默认租户是租户 3，也只允许访问租户 3。
- 租户 4 不是公司当前业务租户，不要尝试读取或切换到租户 4。
- SIM 只提供受控数据工具；桌面 Agent 负责推理、编排、解释和产物组织。

## 工具选择

- 查表清单或字段：先用 `tool_search` 选择 `sim-data-agent_sim_get_table_schema`。
- 查来源、下游影响、ETL 或清洗链路：用 `sim-data-agent_sim_get_table_lineage`。
- 用户说的是业务指标、口径、营收、订单、车辆月补等概念：先用 `sim-data-agent_sim_search_metrics` 和 `sim-data-agent_sim_search_glossary`。
- 用户只给出站点、项目、区域、人员、状态等具体值，但没有说明字段：先用 `sim-data-agent_sim_search_table_values` 定位候选字段，再查表结构确认。
- 需要生成 SQL 但不执行：用 `sim-data-agent_sim_generate_sql_draft`。
- 需要执行查询：用 `sim-data-agent_sim_pgsql_query`，只执行只读 SELECT/WITH。
- 需要导出大量明细：用 `sim-data-agent_sim_export_csv`，不要把大结果粘贴到回复里。

## SQL 安全规则

- SQL 必须是 SELECT 或 WITH。
- 业务表必须显式带租户 schema，例如 `tenant_3_dwd."table_name"`。
- 禁止访问 `tenant_4_*`、`public`、`information_schema`、`pg_catalog` 或跨库三段式表名。
- 禁止 INSERT、UPDATE、DELETE、DROP、ALTER、TRUNCATE、CREATE、GRANT、REVOKE、COPY、CALL、DO、SET。
- 不要猜字段。字段不确定时先查表结构、指标或术语。
- 不要自己追加不存在的 `tenant_id`、`is_delete`、`deleted` 等默认过滤条件。

## 回复方式

- 对业务用户用中文解释口径、使用的表和关键过滤条件。
- 小结果可以摘要展示；大结果只说明导出文件路径、行数和列数。
- 如果工具返回权限或租户错误，直接说明当前桌面连接器只开放租户 3。
