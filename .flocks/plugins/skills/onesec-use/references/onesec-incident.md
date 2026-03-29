# OneSEC 威胁事件详情查看方式

威胁事件详情有两种查看方式，根据需求选择：

| 方式 | 适用场景 | 获取信息量 |
|------|---------|-----------|
| **威胁图**（跳转详情页） | 深度分析单个事件的完整攻击链 | 完整（推荐） |
| **事件概览**（表格行点击展开） | 快速查看事件摘要，无需跳转 | 摘要 |

## 方式一：威胁图 / 事件详情页

```bash
agent-browser --headed open "https://<onesec-domain>/pcedr/threatincidents"
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser --headed open "https://<onesec-domain>/pcedr/threatincidents/incident?umid=<umid>&guid=<guid>"
agent-browser wait --load networkidle
agent-browser get text body
```

详情页 URL 形式：

`/pcedr/threatincidents/incident?umid=<主机ID>&guid=<事件GUID>`

## 方式二：事件概览

优先用 `tbody tr`，不行再用 `data-row-key`：

```bash
agent-browser eval "document.querySelectorAll('tbody tr')[0]?.click()"
agent-browser wait 500
agent-browser get text body
```

```bash
agent-browser eval "document.querySelector('[data-row-key=\"table0\"]')?.click()"
agent-browser wait 500
agent-browser get text body
```

> 事件概览只适合看摘要；需要完整攻击链时，优先用详情页。
