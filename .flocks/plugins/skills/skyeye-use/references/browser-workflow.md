
# SkyEye/天眼/网神分析平台浏览器自动化

> 如果 SkyEye 域名不清楚，先问用户，不要擅自填写。

## 零、登录认证

State 文件路径：`~/.flocks/browser/skyeye/auth-state.json`（固定，全局唯一）。

### 首次登录 / Session 过期重新登录

```bash
# 用 --headed 打开浏览器，人工完成登录（含短信验证码/MFA等）
agent-browser close
agent-browser --headed open "https://<skyeye-domain>/login"
```

等待用户登录结束，收到通知后继续：

```bash
# 登录成功后立即保存 state
agent-browser state save ~/.flocks/browser/skyeye/auth-state.json
```

### CLI 认证失败时的恢复流程

当 CLI 出现以下任一情况，优先判定为认证问题（**不要立刻要求用户重新登录**）：

- 返回 HTTP `401` / `403`
- 返回内容包含 `Unauthorized`、`login`、未登录、认证失败
- `auth-state.json` 存在，但 CLI 请求仍失败

**恢复步骤（最多尝试 1 次）**：

```bash
# 1) 重新加载 state（强制刷新浏览器会话）
agent-browser close
agent-browser state load ~/.flocks/browser/skyeye/auth-state.json

# 2) 访问受保护页面验证
agent-browser open "https://<skyeye-domain>"
agent-browser wait --load networkidle

# 3) 根据结果决策
URL=$(agent-browser get url)
if [[ "$URL" == *"/login"* ]]; then
  echo "Session 仍无效，需重新登录"
  # → 走上方「首次登录 / 重新登录」流程
else
  agent-browser state save ~/.flocks/browser/skyeye/auth-state.json
  echo "Session 已恢复，可重试 CLI"
  # → 重试一次 CLI；若仍失败，再走重新登录，不要无限循环
fi
```

---

## CLI 执行约定

CLI 在 skill 内：

`scripts/skyeye_cli.py`

执行命令时：

1. 优先使用 `uv run python scripts/skyeye_cli.py ...`
2. 认证优先使用浏览器导出的 `auth-state.json`

认证环境变量：

- `SKYEYE_BASE_URL=https://<skyeye-domain>`
- `SKYEYE_AUTH_STATE=~/.flocks/browser/skyeye/auth-state.json`
- 如确实没有 state 文件，再使用 `SKYEYE_CSRF_TOKEN`

### 快速判断

- 用户说"告警列表 / 告警统计"时，用 `alarm list` 或 `alarm count`
- 用户说"日志检索 / 日志分析 / 日志统计 / Lucene / 专家模式 / 字段状态"时，用 `log search`
- 如果用户要传感器侧告警，不要用这个 skill，改用 `skyeye-sensor-data-fetch`

### 常用命令

如果已经通过 `export` 设置好环境变量：

```bash
# 默认输出 JSON
uv run python scripts/skyeye_cli.py alarm list --days 1
uv run python scripts/skyeye_cli.py alarm count --days 1 --filter hazard_level=high,critical
uv run python scripts/skyeye_cli.py log search 'alarm_sip:(10.0.0.1)' --days 1

# 配合 jq 提取字段
uv run python scripts/skyeye_cli.py alarm list --days 1 | jq '.data.items[].threat_name'

# 加 --table 输出格式化表格（人工阅读用）
uv run python scripts/skyeye_cli.py alarm list --days 1 --table
```

带认证的完整单行格式（无需提前 export，适合直接执行）：

```bash
SKYEYE_BASE_URL=https://<skyeye-domain> \
SKYEYE_AUTH_STATE=~/.flocks/browser/skyeye/auth-state.json \
uv run python scripts/skyeye_cli.py \
  alarm list --days 1
```

详细使用方法请阅读 [cli-reference](cli-reference.md)

## CLI 与 agent-browser 配合方式

默认先用 CLI，不要因为页面更直观就直接打开浏览器。
- CLI 负责稳定查询和快速筛选
- `agent-browser` 负责页面详情、导出下载、复杂交互和人工确认
出现以下任一情况时，切到浏览器：
- 需要页面详情
- 需要导出或下载
- 需要复杂交互或联动筛选
- CLI 未覆盖目标能力
- CLI 当前不可用
- 页面需要人工登录、验证码、多因子认证或页面确认
一旦进入浏览器模式，就不要在同一任务里来回切回 CLI。

### 浏览器最小操作模板
```bash
agent-browser open "https://<skyeye-domain>/<path>"
agent-browser wait --load networkidle
agent-browser snapshot -i
```

更多使用方法参考： agent-browser skill

## 边界说明

- 这个 skill 面向 SkyEye 分析平台，不是传感器侧接口
- CLI 只保留 `alarm list`、`alarm count` 和 `log search`
- 传感器侧告警请使用 `skyeye-sensor-data-fetch`

## 重要提醒

- **Session 管理**：详见[零、登录认证](#零登录认证)。任务开始前先确认 `auth-state.json` 存在；CLI 认证失败时先走恢复流程，不要立刻要求用户重新登录。
- **禁止连续失败循环**：同一命令最多重试 2 次；认证恢复流程只走一次，仍失败则提示用户手动重新登录。
  - **以下错误属于需要用户干预的基础设施问题，立即停止所有重试，直接告知用户处理**：
    - `ERR_CERT_AUTHORITY_INVALID`：站点证书不被本机信任，使用 `--ignore-https-errors` 或请求用户处理。
    - `ERR_NAME_NOT_RESOLVED`：域名无法解析，告知用户确认域名或检查 DNS / hosts 配置。