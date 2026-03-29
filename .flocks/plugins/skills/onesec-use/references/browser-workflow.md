
# OneSEC 终端安全平台浏览器自动化

## 零、登录认证

State 文件路径：`~/.flocks/browser/onesec/auth-state.json`（固定，全局唯一）。

### 首次登录 / Session 过期重新登录

```bash
# 用 --headed 打开浏览器，人工完成登录
agent-browser close
agent-browser --headed open "https://<onesec-domain>/login"
```

等待用户登录结束，收到通知后继续：

```bash
# 登录成功后立即保存 state
agent-browser state save ~/.flocks/browser/onesec/auth-state.json
```

### CLI 或页面认证失败时的恢复流程

当出现以下任一情况，优先判定为认证问题：

- 页面被重定向到登录页
- CLI 返回 HTTP `401` / `403`
- CLI 输出包含未登录、认证失败、`Unauthorized`、`login`
- `auth-state.json` 已存在，但 CLI 或页面仍提示无权限

恢复步骤（最多尝试 1 次）：

```bash
# 1) close 并重新加载 state
agent-browser close
agent-browser state load ~/.flocks/browser/onesec/auth-state.json

# 2) 打开受保护页面验证 session
agent-browser open "https://<onesec-domain>/pcedr/dashboard"
agent-browser wait --load networkidle

# 3) 根据结果决策
URL=$(agent-browser get url)
if [[ "$URL" == *"/login"* ]]; then
  echo "Session 仍无效，需重新登录"
else
  agent-browser state save ~/.flocks/browser/onesec/auth-state.json
  echo "Session 已恢复，可重试 CLI 或页面操作"
fi
```

如果仍然落回登录页，再要求用户重新登录，不要无限循环重试。

---

## 一、产品导航与功能模块

> ⚠️ 如果 OneSEC 域名不清楚，请先询问用户，不要擅自填写域名。
> 如找不到功能入口或遇到 404，查阅 [references/onesec-menu.md](references/onesec-menu.md) 获取完整 URL。

**进入页面首选直接拼接 URL**（比菜单点击更稳定）：

```bash
agent-browser open "https://<onesec-domain>/<path>"
agent-browser wait --load networkidle
agent-browser get text body
```

| 模块 | 子功能 | URL 路径 | 主要用途 |
|------|--------|---------|---------|
| **监控和报告** | 概览 | `/monitor/overview` | 系统整体安全态势总览 |
| | 终端安全概览 | `/pcedr/dashboard` | EDR 安全状态总览 |
| | DNS防护概览 | `/onedns/console/dashboard` | DNS 防护状态总览 |
| | 银狐防治 | `/antisilverfox` | 银狐专项治理入口 |
| | 报告中心 | `/onedns/console/reports` | 各类安全报表查看入口 |
| **终端检测与响应 (EDR)** | 威胁事件 | `/pcedr/threatincidents` | EDR 聚合威胁事件列表（事件维度），用于查看事件摘要、判定结果和处置状态 |
| | 检出行为 | `/pcedr/anomalyactivities` | 异常行为检测结果列表，用于查看被检出的可疑行为 |
| | 恶意文件 | `/pcedr/threatfiles` | 恶意文件检测与管理入口 |
| | 日志调查 | `/pcedr/investigation` | EDR 原始告警/行为记录高级查询（日志维度），用于精细筛选和溯源分析 |
| | 响应中心 | `/pcedr/tasks` | 响应任务管理入口（处置维度），包含人工响应和自动响应 |
| | 威胁狩猎 | `/pcedr/threat_hunting` | 主动威胁狩猎场景入口，可联动日志调查 |
| **DNS安全防护** | 域名解析报表 | `/onedns/console/domains` | DNS 解析统计报表 |
| | 域名解析日志 | `/onedns/console/domainLog` | DNS 原始解析记录查询（日志维度） |
| | 安全事件报表 | `/onedns/console/securityincident` | DNS 安全事件统计报表 |
| | 内容分类报表 | `/onedns/console/contentCategory` | 网站内容分类统计报表 |
| | 威胁定位处置 | `/onedns/console/threatMitigation` | DNS 威胁告警定位与处置入口（DNS 告警维度） |
| | VA溯源日志 | `/onedns/console/vaInvestigation` | VA 溯源调查日志 |
| **漏洞补丁管理** | 漏洞管理 | `/vulnerability_manage` | 漏洞清单查询入口（资产维度），含严重级别、CVE 和影响终端 |
| | 补丁管理 | `/patch_manage` | 补丁分发与安装状态管理 |
| **软件安全** | 已安装软件/AI应用 | `/pcedr/softwarelist` | 终端软件资产清单（资产维度），用于查询已安装软件，不属于行为日志 |
| | 软件管控 | `/software_control` | 软件黑白名单与远控软件管控入口 |
| | 软件管控日志 | `/pcedr/software_log` | 软件管控执行记录查询（日志维度） |
| **外设管控** | 外设管控日志 | `/device_control_log` | 外设使用记录查询（日志维度） |
| **组织架构** | 职场/分组管理 | `/groupmanagement` | 职场与分组组织结构管理 |
| **终端接入管理** | 终端管理 | `/pcedr/agent_group` | 终端设备清单与状态查询（资产维度） |
| | 终端策略 | `/pcedr/policies` | 终端安全策略配置入口 |
| | 信任名单 | `/pcedr/whitelist` | 信任文件与信任进程管理 |
| | 自定义IOC/IOA | `/pcedr/ioc` | 自定义威胁指标与检测规则配置 |
| | 终端部署 | `/pcedr/deployment` | Agent 部署管理入口 |
| **DNS接入管理** | 网络出口配置 | `/onedns/console/deployNetworkConfig` | DNS 出口网络配置 |
| | VA部署 | `/onedns/console/sysConfig/vaclientConfig` | VA 设备部署管理 |
| | DNS防护策略 | `/onedns/console/allPolicies` | DNS 防护策略配置入口 |
| | 拦截放行域名 | `/onedns/console/polices/destList` | 域名黑白名单管理 |
| **平台管理** | 开放接口 | `/apiList` | API 接口文档入口 |
| | 登录管理 | `/pcedr/users` | 账号与权限管理 |
| | 通知管理 | `/pcedr/notice` | 消息通知配置 |
| | 审计日志 | `/pcedr/audit_log` | 平台操作审计日志 |
| | 平台配置 | `/platformconfig` | 系统参数配置入口 |
| | 敏感数据加密 | `/pcedr/encrypt_data` | 敏感数据加密配置 |

---

## 二、数据查询与调查

> 进入浏览器模式后，对于查询类诉求，优先阅读 [references/cli-reference.md](cli-reference.md) 并使用本地 CLI，只有在需要详情下钻或复杂交互时才继续页面点击。

### 入口选择说明

OneSEC 中 **事件**、**告警/日志**、**DNS 告警**、**资产数据** 分布在不同页面，必须先判断查询目标再选入口：

| 查询目标 | 使用入口 | 数据维度 |
|---------|---------|---------|
| 查看最新威胁事件、事件总览、处置状态 | 威胁事件 `/pcedr/threatincidents` | **事件**维度，平台已聚合，关注“发生了什么事件、影响哪些终端” |
| 精细查询高危告警、原始行为记录、溯源轨迹 | 日志调查 `/pcedr/investigation` | **告警/日志**维度，关注“具体哪条记录命中、命中了什么条件” |
| 查看 DNS 威胁告警和终端处置 | 威胁定位处置 `/onedns/console/threatMitigation` | **DNS 告警**维度，关注“哪些终端产生 DNS 威胁告警、当前如何处置” |
| 查询 DNS 原始解析记录 | 域名解析日志 `/onedns/console/domainLog` | **DNS 日志**维度，关注“终端解析了什么域名、何时发生” |
| 查看漏洞清单与高危漏洞 | 漏洞管理 `/vulnerability_manage` | **漏洞资产**维度，关注“有哪些漏洞、影响哪些终端” |
| 查询终端已安装软件 | 已安装软件 `/pcedr/softwarelist` | **软件资产**维度，关注“终端装了什么软件”，不是行为日志 |

**核心区别**：
- **威胁事件**：OneSEC 将相关告警和行为聚合后的事件，一个事件通常包含多个告警/证据。
- **告警/日志**：日志调查中的单条威胁、风险或行为记录，适合按字段、时间、终端、进程做精细筛选。
- **DNS 告警**：OneDNS 模块里的独立告警视图，不应与 EDR 威胁事件混用。
- **资产数据**：漏洞、软件、终端清单等静态或半静态数据，不应在日志调查里查。

**意图判定建议**：
- 用户说“最新事件”“看下最近的威胁事件”时，优先进入 `threatincidents`。
- 用户说“最新高危告警”“查某终端的告警日志”时，优先进入 `investigation`。
- 用户明确提到 “DNS 告警” 或 “DNS 威胁”，进入 `threatMitigation` 或 `domainLog`。

---

### 2.1 EDR 威胁事件查询

→ 页面：`/pcedr/threatincidents`

> 事件详情查看的两种方式（威胁图 vs 事件概览）见 [references/onesec-incident.md](references/onesec-incident.md)

适合：查看最新威胁事件、按处置状态筛选、确认影响终端、阅读事件摘要。

#### 默认方式：CLI 直接查询（推荐）

```bash
ONESEC_BASE_URL=https://<onesec-domain> \
ONESEC_AUTH_STATE=~/.flocks/browser/onesec/auth-state.json \
python .flocks/plugins/skills/onesec-use/scripts/onesec_cli.py \
  threat search [--days <N>] [--page <N>] [--page-size <N>] [--keyword "<关键词>"]

ONESEC_BASE_URL=https://<onesec-domain> \
ONESEC_AUTH_STATE=~/.flocks/browser/onesec/auth-state.json \
python .flocks/plugins/skills/onesec-use/scripts/onesec_cli.py \
  threat top [--days <N>] [--limit <N>]
```

适用：

- 看最近威胁行动列表
- 看分页结果
- 看 TOP 威胁名称
- 需要稳定结构化结果而不是页面截图或摘要

只有在需要查看威胁图、事件概览、事件详情页时，才继续页面操作。

页面左侧为**终端维度**列表（按终端聚合的威胁），右侧为**事件列表**（按事件聚合）。

```bash
agent-browser open "https://<onesec-domain>/pcedr/threatincidents"
agent-browser wait --load networkidle
agent-browser get text body
```

**事件列表关键字段**：事件名称、判定结果（APT/黑产/远控/钓鱼/攻击者工具/蠕虫/自定义规则）、处置状态（未处置/处置中/已处置）、MEDR 告警解读、影响终端。

> 这里展示的是**聚合后的事件摘要**和关联告警解读，不是原始告警明细列表。

**查看事件详情（默认方式，威胁图）**：

```bash
# 每行事件有一个跳转链接，直接 open 详情 URL（在 snapshot 中找到 ref 对应的 /url）
agent-browser open "https://<onesec-domain>/pcedr/threatincidents/incident?umid=...&guid=..."
agent-browser wait --load networkidle
agent-browser get text body
```

**查看事件概览（快速方式）**：

```bash
# 点击事件表格行展开概览（index 从 0 开始，[0] 为第1行）
# 如 tbody tr 无效，改用 data-row-key：document.querySelector('[data-row-key="table0"]')?.click()
agent-browser eval "document.querySelectorAll('tbody tr')[0]?.click()"
agent-browser wait 500
agent-browser get text body
```

**顶部筛选**（判定结果、PUA 检测、处置状态等）是自定义组件，需用 eval 操作：

```bash
agent-browser eval "Array.from(document.querySelectorAll('*')).find(el => el.textContent?.trim() === 'APT')?.click()"
```

---

### 2.2 告警日志调查（EDR 原始告警/行为日志，高级查询）

→ 页面：`/pcedr/investigation`

适合：精细筛选高危告警、按终端/IP/Hash/进程路径查询、追踪某终端完整行为轨迹、做溯源分析。

**与威胁事件页的区别**：日志调查查的是每一条告警/日志原始行为记录，而非聚合后的事件。

> 完整字段列表（50+字段）、枚举值和查询语法见 [references/instruction.md](references/instruction.md)

#### 默认方式：CLI 直接查询（推荐）

```bash
ONESEC_BASE_URL=https://<onesec-domain> \
ONESEC_AUTH_STATE=~/.flocks/browser/onesec/auth-state.json \
python .flocks/plugins/skills/onesec-use/scripts/onesec_cli.py \
  log search "<SQL条件>" [--days <N>] [--hours <N>] [--limit <N>]

ONESEC_BASE_URL=https://<onesec-domain> \
ONESEC_AUTH_STATE=~/.flocks/browser/onesec/auth-state.json \
python .flocks/plugins/skills/onesec-use/scripts/onesec_cli.py \
  log types [--days <N>]

ONESEC_BASE_URL=https://<onesec-domain> \
ONESEC_AUTH_STATE=~/.flocks/browser/onesec/auth-state.json \
python .flocks/plugins/skills/onesec-use/scripts/onesec_cli.py \
  log trend [--days <N>]
```

适用：

- 按 SQL 搜索日志
- 最近 N 小时 / N 天日志筛查
- 查看日志类型统计
- 查看日志趋势

只有在需要点击单条记录详情、使用页面 AI 查询、查看联动面板或复杂筛选时，才继续页面操作。

**进入高级查询模式**：

> ⚠️ 高级查询使用字段名直接写条件语句，**必须先查阅 [references/instruction.md](references/instruction.md)** 确认字段名、枚举值和语法，否则查询无效。

```bash
agent-browser open "https://<onesec-domain>/pcedr/investigation"
agent-browser wait --load networkidle

# 点击"高级查询"按钮（按文字定位）
agent-browser eval "Array.from(document.querySelectorAll('button')).find(el => el.textContent?.trim() === '高级查询')?.click()"
agent-browser wait 1000

# 在输入框中填写查询语句（snapshot 获取输入框 ref）
agent-browser snapshot -i
agent-browser fill @eN "查询语句"  # ref 以实际 snapshot 为准

# 点击"查询"执行
agent-browser eval "Array.from(document.querySelectorAll('button')).find(el => el.textContent?.trim() === '查询')?.click()"
agent-browser wait --load networkidle
agent-browser get text body
```

**常用查询示例**：

| 查询场景 | 查询语法 |
|---------|---------|
| 特定终端所有行为 | `host_name = 'LAPTOP-20ECC75'` |
| 特定终端IP | `host_ip = '192.168.0.6'` |
| 只看威胁告警 | `threat.level = 'attack'` |
| 只看高危威胁告警 | `threat.level = 'attack' AND threat.severity = '3'` |
| 特定威胁名称 | `threat.name LIKE '%勒索%'` |
| 特定进程路径 | `proc_file.path LIKE '%AppData%Temp%'` |
| 可疑命令行（PowerShell编码） | `proc.cmdline LIKE '%powershell%' AND proc.cmdline LIKE '%-enc%'` |

查询结果按 **全部 / 威胁 / 风险 / 攻击面收敛** Tab 分类展示，点击具体条目可查看完整字段详情。

**使用 AI 查询**（输入自然语言 → 生成 SQL → 一键填入 → 查询）：

```bash
# 第1步：打开 AI 查询面板
agent-browser eval "Array.from(document.querySelectorAll('*')).filter(el => el.textContent?.includes('AI查询') && el.tagName === 'BUTTON')[0]?.click()"
agent-browser wait 1000
agent-browser snapshot -i

# 第2步：在输入框中填写自然语言描述（面板内的 textarea/input）
agent-browser fill @eN "查询最近一周内所有高危威胁日志"  # ref 以实际 snapshot 为准

# 第3步：点击"生成SQL"按钮
agent-browser eval "Array.from(document.querySelectorAll('button')).find(el => el.textContent?.trim() === '生成SQL')?.click()"

# 第4步：等待 AI 推理并生成 SQL（有推理过程文字出现后再继续）
agent-browser wait --text "一键填入"

# 第5步：点击"一键填入"将生成的 SQL 填入查询框
agent-browser eval "Array.from(document.querySelectorAll('*')).find(el => el.textContent?.trim() === '一键填入')?.click()"
agent-browser wait 500

# 第6步：点击"查询"执行
agent-browser eval "Array.from(document.querySelectorAll('button')).find(el => el.textContent?.trim() === '查询')?.click()"
agent-browser wait --load networkidle
agent-browser get text body
```

---

### 2.3 DNS 查询与告警处置

#### 域名解析日志

→ 页面：`/onedns/console/domainLog`

按终端内网 IP、终端名称、MAC 地址、DNS 查询域名、威胁类型、组内资产标记、时间范围等条件查询 DNS 解析记录。

适合：还原某终端访问过哪些域名、核查某域名何时被解析、查询 DNS 原始日志。

#### 威胁定位处置

→ 页面：`/onedns/console/threatMitigation`

左侧为**威胁终端列表**，右侧为**威胁告警**（含严重级别、威胁名称、威胁类型、响应状态）。支持对终端下发处置任务。

适合：查看最新 DNS 威胁告警、按终端定位 DNS 风险、联动做 DNS 处置。

---

### 2.4 资产与配置查询

#### 漏洞管理

→ 页面：`/vulnerability_manage`

分 **Windows** 和 **信创** 两个 Tab，展示漏洞编号（CVE）、漏洞名称、影响应用、严重级别（高危/中危）、CVSS 评分、修复方式、涉及终端数。

适合：查看高危漏洞、按 CVE 检索、确认受影响终端范围。

#### 已安装软件（软件资产查询）

→ 页面：`/pcedr/softwarelist`

> ⚠️ **查询终端上安装了哪些软件，应使用此页面，而非日志调查。** 此页面展示的是资产数据（软件清单），日志调查展示的是行为记录。

#### 终端管理

→ 页面：`/pcedr/agent_group`

左侧为**职场/分组树**，右侧为终端列表（IP/MAC 地址、用户信息、所属职场/分组、当前生效策略、在线状态）。支持按分组筛选。

#### 终端策略

→ 页面：`/pcedr/policies`

顶部有多个 Tab：**基础**、安全通用、EDR、OneDNS、威胁防护、漏洞补丁管理、软件管控、外设管控、攻击面收敛。切换 Tab 查看不同策略配置。

---

### 2.5 响应与威胁狩猎

#### 响应中心

→ 页面：`/pcedr/tasks`

分 **人工响应** 和 **自动响应** 两个 Tab，展示响应任务列表（任务ID、下发对象、任务类型、任务目标、任务状态、执行信息）。

**任务类型**：同步资产信息、漏洞扫描、恶意文件查杀等。

```bash
agent-browser open "https://<onesec-domain>/pcedr/tasks"
agent-browser wait --load networkidle
# 切换到"自动响应" Tab
agent-browser eval "Array.from(document.querySelectorAll('*')).find(el => el.textContent?.trim() === '自动响应')?.click()"
agent-browser wait 1000
agent-browser get text body
```

#### 威胁狩猎

→ 页面：`/pcedr/threat_hunting`

提供内置狩猎场景（执行与下载行为类、信息探测与收集、系统配置篡改、权限控制与突破等），可跳转至日志调查继续查看原始记录。

```bash
agent-browser open "https://<onesec-domain>/pcedr/threat_hunting"
agent-browser wait --load networkidle
agent-browser get text body
# 点击具体场景展开（折叠面板，需 eval）
agent-browser eval "const el = document.evaluate('//*[contains(text(),\"执行与下载\")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; if(el) el.click();"
```


---

## 三、浏览器操作技巧

**核心原则**：OneSEC 是 SPA（React/Ant Design），自定义组件（div/span onClick）**无法被 `agent-browser click` 直接点击**，**都可以用 `agent-browser eval` 点击**。

**`agent-browser click` 失败时**，立即改用 eval（不要重试 click）：

```bash
# 方式1：用 -C 发现可交互元素（cursor:pointer/onclick），再用 CSS 选择器点击（不要用 ref）
agent-browser snapshot -i -C
# 输出示例: - clickable "导出" [ref=e200] [cursor:pointer, onclick] class="export-btn"
# 从输出中读取 class 名，构造 CSS 选择器点击（class 比 ref 更稳定）：
agent-browser eval "document.querySelectorAll('.<从输出中获取的class>')[0]?.click()"

# 方式2：XPath 文本定位（文字唯一时优先）
agent-browser eval "document.evaluate('//*[contains(text(),\"目标文字\")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue?.click()"

# 方式3：遍历查找（多个同名元素或精确匹配）
agent-browser eval "Array.from(document.querySelectorAll('*')).find(el => el.textContent?.trim() === '目标文字')?.click()"

# 方式4：先打印 DOM 调试，再构造选择器
agent-browser eval "Array.from(document.querySelectorAll('*')).filter(el => el.textContent?.trim().includes('目标文字') && el.textContent?.trim().length < 40).forEach(el => console.log(el.tagName, el.className, el.outerHTML.substring(0, 200)))"
```

**`eval --stdin` heredoc（复杂 JS 避免 shell 引号破坏）**：

```bash
# 当 eval 表达式含嵌套引号、箭头函数、模板字符串时，用 heredoc 避免 shell 解析破坏
agent-browser eval --stdin <<'EVALEOF'
Array.from(document.querySelectorAll('*')).find(
  el => el.textContent?.trim() === '目标文字' &&
        window.getComputedStyle(el).cursor === 'pointer'
)?.click()
EVALEOF
```

**语义定位器 `find`（比 eval 更简洁，优先尝试）**：

```bash
agent-browser find text "高级查询" click           # 按文字找并点击
agent-browser find role button click --name "查询"  # 按 role + name
agent-browser find placeholder "输入查询内容" fill "查询语句"  # 按 placeholder 填表
```

**`wait --fn` 等待 JS 条件（比固定 wait 毫秒更可靠）**：

```bash
agent-browser wait --fn "document.querySelectorAll('tbody tr').length > 0"  # 等表格有数据
agent-browser wait --fn "!document.querySelector('.ant-spin')"               # 等 loading 消失
agent-browser wait --fn "document.querySelector('.ant-result')"              # 等结果出现
```

**导航首选直接拼 URL**（SPA 路由，URL 跳转比菜单点击更稳定）：

```bash
agent-browser open "https://<onesec-domain>/path"
agent-browser wait --load networkidle
```

**必须使用 JavaScript 滚动**：

```bash
agent-browser eval "window.scrollTo(0, document.body.scrollHeight)"   # 滚到底部
agent-browser eval "window.scrollBy(0, 1000)"                          # 滚动指定像素
```

**表格行点击**：OneSEC 使用 Ant Design 表格，优先用 `tbody tr`，不行再用 `data-row-key`：

```bash
# 方式1：标准 tbody tr（优先）
agent-browser eval "document.querySelectorAll('tbody tr')[0]?.click()"

# 方式2：data-row-key 属性（行索引从 table0 开始）
agent-browser eval "document.querySelector('[data-row-key=\"table0\"]')?.click()"

# 保底：先调试确认实际行结构，再选择方式
agent-browser eval "const rows = document.querySelectorAll('tbody tr'); console.log('行数:', rows.length, '结构:', rows[0]?.outerHTML?.substring(0,150))"
```

**关闭 Ant Design 弹窗**：

```bash
agent-browser eval "document.querySelector('.ant-modal-close')?.click()"
```

### 定位不到元素时：调试技巧

```bash
# 查看页面所有 a/button 的文本
agent-browser eval "Array.from(document.querySelectorAll('a, button')).forEach(el => console.log(el.tagName, el.textContent?.trim().substring(0,30)))"

# 确认表格行数及结构（保底调试）
agent-browser eval "const rows = document.querySelectorAll('tbody tr'); console.log('行数:', rows.length, rows[0]?.outerHTML?.substring(0,150))"
```

---

## 四、重要提醒

1. **refs 生命周期**：每次点击/滚动/页面变化后，`@eN` refs 会失效，必须重新 `snapshot -i`

2. **优先直接拼 URL**：OneSEC 菜单使用 SPA 路由，`agent-browser open <url>` 比点击菜单更稳定可靠。

3. **等待加载**：导航或操作后，务必执行 `wait --load networkidle` 等待页面完全加载

4. **使用 headed 模式**：除非用户明确要求，默认使用 `--headed` 参数：
   ```bash
   agent-browser --headed open <url>
   ```

5. **不要主动关闭浏览器**：除非用户明确要求，否则不要执行 `agent-browser close` 关闭当前浏览器会话。

6. **滚动必须用 JavaScript**：`agent-browser scroll` 无法触发动态内容加载

7. **列表只展示摘要**：威胁事件、漏洞、补丁等列表只展示摘要，需点击进入详情获取完整信息

8. **查询优先级**：浏览器模式下，如果需求只是拉列表、跑 SQL、看趋势或统计，优先使用 [references/cli-reference.md](cli-reference.md) 中的 CLI，不要直接开始页面点击。

---

## 附加资源

- **OneSEC 完整菜单结构与 URL 映射**：[references/onesec-menu.md](onesec-menu.md)
  - 遇到 404、找不到功能入口时查阅，涵盖所有模块的完整路径
- **威胁事件详情查看方式**：[references/onesec-incident.md](onesec-incident.md)
  - 威胁图（跳转详情页）和事件概览（表格行点击）两种查看方式的操作说明
- **日志调查字段说明与高级查询**：[references/instruction.md](instruction.md)
  - 日志调查高级查询的全量字段（JSON路径）、枚举值、常用查询示例
- **OneSEC CLI 参考**：[references/cli-reference.md](cli-reference.md)
  - 浏览器模式下优先使用的 5 个查询接口，含认证方式、调用示例和返回字段说明
