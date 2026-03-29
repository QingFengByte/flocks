# TDP 浏览器操作详细技巧

## 1. 导航操作

### 推荐方式：直接拼接 URL 跳转

TDP 是 SPA 应用，直接跳转 URL 比点击菜单更稳定：

```bash
agent-browser open "https://<tdp-domain>/dashboard"
agent-browser wait --load networkidle
agent-browser snapshot -i
```

### 菜单点击（需要先获取 refs）

> ⚠️ refs 是动态生成的，每次页面加载后编号都会变化，必须先 `snapshot -i` 获取当前实际 ref。

```bash
# 先获取当前页面 refs
agent-browser snapshot -i

# 点击目标菜单（ref 以实际 snapshot 结果为准，示例仅为示意）
agent-browser click @e1
agent-browser wait --load networkidle

# 每次操作后需重新获取 refs
agent-browser snapshot -i
```

---

## 2. 页面滚动

> ⚠️ **必须使用 JavaScript 滚动**，`agent-browser scroll` 命令无法触发 TDP 动态加载的内容。

```bash
# 获取页面总高度（判断是否还有更多内容）
agent-browser eval "document.body.scrollHeight"

# 滚动到底部（推荐，可触发动态加载）
agent-browser eval "window.scrollTo(0, document.body.scrollHeight)"

# 分步滚动（每次滚动后截图确认内容）
agent-browser eval "window.scrollBy(0, 1000)"
agent-browser snapshot -i

# 滚动到指定元素
agent-browser eval "const el = document.evaluate('//*[contains(text(),\"目标文字\")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; if(el) el.scrollIntoView();"
```

**判断是否需要继续滚动的依据**：
- 快照中显示的内容较少，页面有大量空白
- 看到"查看更多"、"加载更多"等链接
- 页面布局明显不完整（如被截断的表格）
- 没有看到预期的数据列表

---

## 3. 动态元素点击

TDP 使用 React/Vue 构建，大量元素是 `<div>/<span>` + onClick，`snapshot -i` 无法捕获。

### 方法一：XPath 文本定位（适合文本唯一的元素）

```bash
# 通过文本精确定位并点击
agent-browser eval "const el = document.evaluate('//*[contains(text(),\"Redis\")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; if(el) el.click();"

# 在特定容器内查找
agent-browser eval "const el = document.evaluate('//div[@class=\"menu\"]//span[contains(text(),\"日志分析\")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue; if(el) el.click();"
```

### 方法二：表格行点击（告警列表、事件列表）

```bash
# 点击第一条数据行（如果用 `tr` 选择器，index 1 通常跳过表头）
agent-browser eval "document.querySelectorAll('tr')[1].click()"

# 点击 tbody 中的第一条数据行（更精确，避免选中表头）
agent-browser eval "document.querySelectorAll('tbody tr')[0]?.click()"

# 点击第 N 条数据行（从 0 开始）
agent-browser eval "document.querySelectorAll('tbody tr')[N]?.click()"
```

### 方法三：遍历所有元素（适合折叠面板、Tab切换、动态按钮）

当 XPath 无法定位，或目标元素有可点击的子元素时使用：

```bash
# 等待页面渲染完成
agent-browser wait 2000

# 遍历所有元素，按文本内容定位并点击子按钮
agent-browser eval "for(const el of document.querySelectorAll('*')) { const txt = el.textContent?.trim(); if(txt?.includes('目标文本')) { const btn = el.querySelector('button, svg, [role=button]'); if(btn) { btn.click(); break; } } }"

# 等待展开/跳转完成
agent-browser wait 1000

# 获取结果
agent-browser get text body
```

### 方法四：查找链接（"查看详情"等文字链接）

```bash
# 查找并点击第一个包含特定文字的链接
agent-browser eval "Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('查看详情'))?.click()"

# 关闭弹窗（Ant Design Modal）
agent-browser eval "document.querySelector('.ant-modal-close')?.click()"
```

### 定位策略选择表

| 场景 | 推荐方式 |
|------|----------|
| 文本唯一的元素 | XPath `contains(text(),'关键词')` |
| 多个相似元素，需精确匹配 | `textContent.match(/正则/)` |
| 父元素含多个子按钮 | 先定位父，再 `querySelector('button, svg, [role=button]')` |
| class 名动态变化 | 用标签名 `button, svg, [role=button]` 而非 class |
| 表格数据行 | `querySelectorAll('tbody tr')[index].click()` |
| 文字链接 | `Array.from(querySelectorAll('a')).find(...)` |

---

## 4. 调试技巧（定位不到元素时）

```bash
# 打印页面内所有包含目标文字的元素信息
agent-browser eval "for(const el of document.querySelectorAll('*')) { const txt = el.textContent?.trim(); if(txt && txt.includes('目标文本') && txt.length < 50) { console.log(el.tagName, el.className, el.outerHTML.substring(0, 300)); } }"

# 查看页面所有可点击元素（a/button）
agent-browser eval "Array.from(document.querySelectorAll('a, button')).forEach(el => console.log(el.tagName, el.textContent?.trim().substring(0,30), el.href || ''))"

# 检查元素是否存在
agent-browser eval "console.log('found:', document.querySelectorAll('tr').length, 'rows')"
```

---

## 5. 截图保存

```bash
# 截取当前视口
agent-browser screenshot

# 截取完整页面（包含滚动内容）
agent-browser screenshot --full

# 带标注的截图（显示元素编号，用于确认 ref）
agent-browser screenshot --annotate
```

---

## 6. 注意事项

- **等待时间**：执行 `eval` 前确保 DOM 渲染完成，页面交互后用 `wait --load networkidle` 或 `wait <ms>`
- **文本匹配精度**：匹配词要足够精确，避免误触相似元素；`textContent` 包含子元素文本，注意嵌套层级
- **refs 失效**：每次滚动、点击或页面变化后 `@eN` refs 都会失效，必须重新 `snapshot -i`
- **获取页面内容**：`agent-browser get text body` 获取纯文本；`snapshot -i` 获取可交互元素列表
