
# TDP 威胁检测平台浏览器自动化

## 零、登录认证

State 文件路径：`~/.flocks/browser/tdp/auth-state.json`（固定，全局唯一）。

### 首次登录 / Session 过期重新登录

```bash
# 用 --headed 打开浏览器，人工完成登录（含短信验证码/MFA等）
agent-browser close
agent-browser --headed open "https://<tdp-domain>/login"
```

等待用户登录结束，收到通知后继续
```bash
# 登录成功后立即保存 state
agent-browser state save ~/.flocks/browser/tdp/auth-state.json
```

### CLI 认证失败时的恢复流程

当 CLI 调用出现以下任一情况，优先判定为认证问题（**不要立刻要求用户重新登录**）：
- 返回 HTTP `401` / `403`
- 返回内容包含 `Unauthorized`、`login`、未登录、认证失败
- `auth-state.json` 存在，但 CLI 请求仍失败

**恢复步骤（最多尝试 1 次）**：

```bash
# 1) close 并重新加载 state（强制刷新浏览器会话）
agent-browser close
agent-browser state load ~/.flocks/browser/tdp/auth-state.json

# 2) 访问受保护页面验证
agent-browser open "https://<tdp-domain>/dashboard"
agent-browser wait --load networkidle

# 3) 根据结果决策
URL=$(agent-browser get url)
if [[ "$URL" == *"/login"* ]]; then
  echo "Session 仍无效，需重新登录"
  # → 走上方「首次登录 / 重新登录」流程
else
  agent-browser state save ~/.flocks/browser/tdp/auth-state.json
  echo "Session 已恢复，可重试 CLI"
  # → 重试一次 CLI；若仍失败，再走重新登录，不要无限循环
fi
```

---

## 一、产品导航与功能模块

**进入页面首选直接拼接 URL**（比菜单点击更稳定）：

```bash
agent-browser open "https://<tdp-domain>/<path>"
agent-browser wait --load networkidle
agent-browser get text body
```

| 模块 | 子功能 | URL 路径 | 主要用途 |
|------|--------|---------|---------|
| **监控** | 首页/仪表板（默认） | `/dashboard` | 安全态势总览：告警趋势、失陷主机、TOP威胁 |
| **威胁** | 威胁事件对应的告警主机（默认） | `/hosts` | 被告警命中的主机列表，含告警次数和类型 |
| | 全部威胁→实时监控 | `/threatMonitor` | 威胁事件查询入口，支持高级查询 |
| | 外部攻击→智能聚合 | `/attack` | 外部攻击事件聚合视图（按事件维度） |
| | 外部攻击→外部攻击 | `/incidents/external` | 外部攻击威胁事件列表 |
| | 内网渗透→内网聚合 | `/lateralconverge` | 内网横向移动事件聚合 |
| | 内网渗透→内网渗透 | `/incidents/lateral` | 内网渗透威胁事件列表 |
| | 失陷破坏 | `/incidents/compromise` | 失陷主机的对外通信/C2连接 |
| | 蜜罐诱捕 | `/hfish` | 蜜罐命中记录，含攻击来源IP和攻击手法 |
| **资产&风险** | 全部服务（默认） | `/asset/serviceList` | 宽泛查询所有服务，左侧分类列表可按类型筛选 |
| | Web应用/框架 | `/asset/webapp` | Web资产，含框架指纹（OA/CMS/管理工具等） |
| | 域名资产 | `/asset/domains` | 内部域名，含解析IP/是否对外开放 |
| | 登录入口 | `/asset/loginApi` | 所有暴露的登录口（SSH/RDP/数据库/FTP/Web），含弱口令/爆破统计 |
| | 主机资产 | `/asset/allDevices` | 全部主机，含服务/Web框架/对外开放情况 |
| | 上传接口 | `/asset/uploadApi` | 文件上传接口，含是否被攻击/存在上传漏洞 |
| | API | `/risk/api` | API列表，含敏感信息类型（身份证/银行卡/AK·SK） |
| | 云服务 | `/cloudService` | 内网主机访问公有云的流量分析 |
| | 脆弱性 | `/asset/vulnerability` | 漏洞/配置不当/访问风险，按严重级别和主机数 |
| | 弱口令 | `/asset/weakPwd` | 弱口令检测结果，含已成功登录记录 |
| | 敏感信息 | `/asset/sensitive` | 传输中的敏感数据（身份证/手机/邮箱/银行卡） |
| | 风险策略配置 | `/asset/riskPolicies` | 自定义风险告警规则（端口开放/异常登录等） |
| **调查** | 日志分析 | `/investigation/logquery` | 原始告警日志高级查询（SPL语法） |
| | 跟踪与狩猎 | `/hunting` | 基于IP/域名/Hash的威胁狩猎 |
| | 攻击者分析 | `/attacker` | 分析特定攻击者IP的攻击行为全貌 |
| **处置** | 取证溯源 | `/endpoint_forensics` | 对失陷主机发起取证，获取终端行为记录 |

---

> 如找不到功能入口或遇到 404，查阅 [tdp-menu.md](tdp-menu.md) 获取完整 URL。

## 二、数据查询与调查

> 写 CLI 查询前，先查 [cli-reference.md](cli-reference.md) 确认命令、参数和常用示例；如果 SQL 字段、枚举值或操作符不确定，再查 [instruction.md](instruction.md)。不要凭记忆臆测字段名。

### 入口选择说明

**威胁事件** 和 **告警日志** 是两个不同维度的数据，优先使用 CLI 调用，只在需要查看原始报文时才用浏览器：

| 查询目标 | 推荐入口 | 数据维度 |
|---------|---------|---------|
| 查看/筛选威胁事件总览（按类型、方向、严重级别、时间） | **CLI `monitor threats`** → 浏览器 `/threatMonitor` | **事件**维度，TDP已聚合，一条 = 一个威胁事件，含检出次数 |
| 精细条件查询原始告警日志（按 IP、端口、URL、payload） | **CLI `logs search`** → 浏览器 `/investigation/logquery` | **告警**维度，未聚合，一条 = 一条原始告警记录 |
| 查看 PCAP / 原始报文 | 浏览器点击告警详情（仅此方式） | 原始数据 |

**用词识别规则（必须遵守）**：
- 用户说"**告警**"、"**告警记录**"、"**告警日志**"、"**最近 X 小时/天的告警**" → **一律走 `告警日志查询`**
- 用户说"**威胁事件**"、"**攻击事件**"、"**有哪些事件**" → 走 `事件查询`
- 未明确区分时：**默认走 `告警日志查询`**，除非用户明确要求"事件聚合"或"事件总览"

---

### 2.1 告警日志调查（原始告警日志，SQL查询）

查的是每一条原始检测记录，而非聚合后的事件。适合：精细条件筛选、查某事件关联的所有原始告警、分析某 IP 的完整行为轨迹。

#### 默认方式：CLI 直接调用 API（推荐）

比浏览器操作更稳定，**优先用此方式**。默认返回的是与页面列表一致的常用字段；只有在**明确指定 `--full`**，或**按指定告警 `threat.id` 拉单条详情**时，才使用全字段模式：

```bash
THREATBOOK_BASE_URL=https://<tdp-domain> \
THREATBOOK_COOKIE_FILE=~/.flocks/browser/tdp/auth-state.json \
THREATBOOK_SSL_VERIFY=false \
python scripts/tdp_cli.py \
  logs search [--sql "<SQL条件>"] [时间参数] [--limit <条数>]
```

**时间参数**（三选一，优先级从高到低）：
- `--from "2026-03-10 09:00" --to "2026-03-10 18:00"`：指定任意时间段（支持 `时间戳 / 日期 / 日期+时间`，UTC+8）
- `--hours 6`：最近 N 小时
- `--days 3`：最近 N 天（默认 1）

**其他参数**：
- `--sql` / `-s`：SQL 过滤条件（也可作为位置参数传入）
- `--limit`：显示条数，默认 20
- `--net-data-type`：流量类型，默认 `attack risk action`，可多次指定
- `--full` / `-f`：全字段模式。**仅在明确要求完整字段，或按 `threat.id` 查询单条告警详情/分析告警时使用**
- 默认输出原始 JSON；如需 Rich 表格输出，显式加 `--table-output`

**使用原则**：
- 常规批量筛查、统计、溯源入口定位：使用默认字段模式，不开 `--full`
- 只有用户明确要求“完整字段/全部字段/详情模式”，或你已经拿到具体 `threat.id` 要查看单条告警详情/分析告警时，才加 `--full`

常见示例：
```sql
-- 查询攻击成功告警
threat.level = 'attack' AND threat.result = 'success'
```

> CLI 用法和查询示例见 [cli-reference.md](cli-reference.md)


#### 备用方式：浏览器操作（需查看 PCAP / 原始报文时使用）

```bash
agent-browser open "https://<tdp-domain>/investigation/logquery"
agent-browser wait --load networkidle
# 点击"高级查询"
agent-browser find text "高级查询" click
agent-browser wait --load networkidle
# 填入查询语句并执行
agent-browser find placeholder "请输入查询语句" fill "查询语句"
agent-browser find text "查询" click
agent-browser wait --fn "document.querySelectorAll('tbody tr').length > 0"
```

点击具体日志条目可查看完整的 HTTP 请求/响应、PCAP 原始报文等详细信息。

---

### 2.2 威胁事件查询

查询**已聚合的威胁事件**（一条记录 = 一个事件，含检出次数、攻击者、受害主机等汇总信息）。

#### 默认方式：CLI 直接调用 API（推荐）

比浏览器操作更稳定、返回完整数据，**优先用此方式**：

```bash
THREATBOOK_BASE_URL=https://<tdp-domain> \
THREATBOOK_COOKIE_FILE=~/.flocks/browser/tdp/auth-state.json \
THREATBOOK_SSL_VERIFY=false \
python scripts/tdp_cli.py \
  monitor threats [--sql "<SQL条件>"] [时间参数] [--limit <条数>]
```

**时间参数**（三选一，优先级从高到低）：
- `--from "2026-03-10 09:00" --to "2026-03-10 18:00"`：指定任意时间段（支持 `时间戳 / 日期 / 日期+时间`，UTC+8）
- `--hours 6`：最近 N 小时
- `--days 3`：最近 N 天（默认 1）

**其他参数**：
- `--sql` / `-s`：SQL 过滤条件，默认 `(threat.level IN ('attack')) AND threat.type NOT IN ('recon')`
- `--limit` / `-l`：显示条数（等同于 `--page-size`），默认 20
- `--page` / `--page-size`：分页控制，默认第1页每页20条
- 默认输出原始 JSON；如需 Rich 表格输出，显式加 `--table-output`


> CLI 用法和查询示例见 [cli-reference.md](cli-reference.md)


#### 备用方式：浏览器操作（需交互式探索或查看页面详情时使用）

> 当查询涉及时间范围时，优先通过 URL 操作，需要把用户要求转为时间戳查询（UTC+8时区）。
> 示例：`<url>?time_from=<start_timestamp>&time_to=<end_timestamp>`

```bash
agent-browser open "https://<tdp-domain>/threatMonitor"
agent-browser wait --load networkidle
# 点击"高级查询"，ref 以实际 snapshot 为准
agent-browser snapshot -i
agent-browser click @eN
```

#### 特定类型威胁事件入口（浏览器）

**外部攻击事件**（外部对内网的攻击）
→ `/attack`（按事件聚合视图）或 `/incidents/external`（原始事件列表）

**内网渗透事件**（内网主机之间的横向移动）
→ `/lateralconverge`（按事件聚合视图）或 `/incidents/lateral`（原始事件列表）

**失陷破坏**（已失陷主机的对外通信）
→ `/incidents/compromise`

---


### 2.3 资产查询

#### 资产攻击面

| 功能 | URL | 说明 |
|------|-----|------|
| 全部服务 | `/asset/serviceList` | 服务汇总（数据库/Web/远程登录/认证等）；左侧分类是自定义组件，需用 eval 切换（见三） |
| Web 应用 | `/asset/webapp` | 框架指纹（Spring/Shiro/OA/CMS等）、对外开放、关联 URL |
| 数据库资产 | `/asset/serviceList` 左侧"数据库"分类 | 查有哪些数据库服务在运行；查攻击告警用 `logs search "net.app_proto IN ('mysql','redis','oracle') AND threat.level = 'attack'"` |
| 域名资产 | `/asset/domains` | 内部域名、解析IP，可过滤是否对外开放 |
| 登录入口 | `/asset/loginApi` | 所有暴露的认证入口（SSH/RDP/Web/数据库），重点看爆破/弱口令数量 |
| 主机资产 | `/asset/allDevices` | 全部主机，含服务、Web框架、开放端口 |
| 上传接口 | `/asset/uploadApi` | 重点关注"对外开放"和"存在风险"标记 |
| API | `/risk/api` | 含敏感信息的 API（身份证/银行卡/AK·SK） |

#### 风险查询

| 功能 | URL | 说明 |
|------|-----|------|
| 脆弱性 | `/asset/vulnerability` | 漏洞/配置不当/访问风险，含受影响主机数和严重级别 |
| 弱口令 | `/asset/weakPwd` | 重点关注**登录结果为"成功"**的条目（已被利用） |
| 敏感信息 | `/asset/sensitive` | 传输中检测到的敏感数据，可按身份证/手机/邮箱过滤 |

---

## 三、浏览器操作原则

> 浏览器只用于以下场景：查看 PCAP / 原始报文 / 页面详情，或 CLI 无法完成的交互式探索。复杂定位、调试、截图时再阅读 [browser-tips.md](browser-tips.md)。

1. **优先直接拼 URL**：TDP 是 SPA，`agent-browser open "https://<tdp-domain>/<path>"` 比菜单点击更稳定。
2. **定位优先级**：优先使用 `find`；`find` 不适用或失败时再用 `eval`。不要在同一个目标上反复重复 `click`。
3. **自定义组件处理**：TDP 大量按钮/Tab/折叠项是自定义组件，`click` 失败很常见；失败后立即改用 `eval`，不要继续重试相同点击。
4. **等待规则**：导航后用 `wait --load networkidle`；动态表格、异步结果、loading 消失等场景优先用 `wait --fn`。
5. **滚动规则**：只能使用 JavaScript 滚动；`agent-browser scroll` 不能可靠触发 TDP 的动态加载。
6. **refs 生命周期**：每次点击、滚动或页面变化后，`@eN` refs 都会失效，必须重新 `snapshot -i`。
7. **需要继续下钻时的判断**：如果列表内容被截断、页面有大量空白、出现“加载更多”，或还没看到预期数据，应继续滚动、展开或进入详情，而不是基于当前摘要下结论。

常用最小模板：

```bash
# 导航后等待页面稳定
agent-browser open "https://<tdp-domain>/<path>"
agent-browser wait --load networkidle

# 文本/输入框优先用 find
agent-browser find text "高级查询" click
agent-browser find placeholder "输入查询内容" fill "查询语句"

# 动态结果优先用 wait --fn
agent-browser wait --fn "document.querySelectorAll('tbody tr').length > 0"
```

---

## 四、重要提醒

1. **必须查看告警详情**：列表页只展示摘要，必须点击条目进入详情才能获取完整的 HTTP 请求/响应、原始报文、PCAP 等信息

2. **结论必须基于详细数据**：调查和溯源场景中，列表摘要信息不足以支撑结论。需遵循以下原则：
   - 在下判断前必须点击进入事件/告警详情，确认攻击结果（success/failed）、payload 内容、原始报文等关键字段
   - 一个事件包含多条告警时，需抽查关键告警明细，不能只看第一条
   - 数据不足或信息不明确时，继续点击获取更多明细，**不基于摘要推断结论**

3. **等待加载**：导航或操作后，务必执行 `wait --load networkidle` 等待页面完全加载

4. **使用 headed 模式**：除非用户明确要求，默认使用 `--headed` 参数：
   ```bash
   agent-browser --headed open <url>
   ```

5. **不要主动关闭浏览器**：除非用户明确要求，否则不要执行 `agent-browser close` 关闭当前浏览器会话。

6. **查询结果为空时直接告知用户**：若页面显示无数据或表格为空，不要反复调整条件重试，直接告诉用户当前条件下查询结果为空即可。
   - **严禁擅自修改查询条件**：用户要求“最近 1 小时”就只查最近 1 小时，不能自行扩大到最近 6 小时、24 小时或更长时间范围
   - **严禁擅自放宽过滤条件**：不能自行删减 SQL 条件、改关键词、改 IP、改资产范围、改事件类型来“试试看有没有数据”
   - 返回结果必须忠实反映用户原始条件；若无数据，直接明确告知“按当前条件未查到结果”

7. 当查询涉及时间范围时，且使用浏览器操作，优先通过 URL 操作，需要把用户要求转为时间戳查询（UTC+8时区）。
> 示例：`<url>?time_from=<start_timestamp>&time_to=<end_timestamp>`
>
> 时间戳转换：
> ```python
> from datetime import datetime, timezone, timedelta
> utc8 = timezone(timedelta(hours=8))
> start_local = datetime(2026, 3, 10, 16, 0, 0, tzinfo=utc8)
> end_local   = datetime(2026, 3, 10, 17, 0, 0, tzinfo=utc8)
> print(int(start_local.astimezone(timezone.utc).timestamp()))
> print(int(end_local.astimezone(timezone.utc).timestamp()))
> ```

8. **Session 管理**：详见[零、登录认证](#零登录认证)。任务开始时先验证 session 有效性再执行任务；CLI 认证失败时先走恢复流程，不要立刻重新登录。

9. **禁止连续失败循环**：
   - 同一个目标操作最多尝试 **3 次**
   - 第一次失败后，必须更换方法（例如 `click` 改 `eval`），不要重复同样操作
   - 同一页面连续失败达到 **5 次**，直接停止本页面操作，不再继续尝试
   - **以下错误属于需要用户干预的基础设施问题，立即停止所有重试，直接告知用户处理**：
     - `ERR_CERT_AUTHORITY_INVALID`：TDP 站点证书不被本机信任，使用--ignore-https-errors 或 请求用户处理。
     - `ERR_NAME_NOT_RESOLVED`：TDP 域名无法解析。告知用户确认域名是否正确，或检查 DNS / hosts 配置。

## 附加资源

- **CLI 参考**：[cli-reference.md](cli-reference.md)
  - 威胁事件查询（`monitor threats`）和告警日志搜索（`logs search`）完整说明，含请求体结构、参数说明、SQL 字段速查表、常用查询示例
- **事件详情查看与分析**：[event-detail.md](event-detail.md)
  - 浏览器点击进入事件/告警详情的操作路径、告警分析要点（攻击结果/payload/PCAP）
- **TDP 完整菜单结构与 URL 映射**：[tdp-menu.md](tdp-menu.md)
  - 遇到 404、找不到功能入口时查阅，涵盖所有模块的完整路径
- **高级查询字段和操作符说明**：[instruction.md](instruction.md)
  - TDP 官方字段定义和操作符说明（60+ 字段原始文档）
- **浏览器操作详细技巧**：[browser-tips.md](browser-tips.md)
  - 动态元素点击进阶方法、调试技巧、截图操作
