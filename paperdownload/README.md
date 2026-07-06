# PaperDownload

依据 DOI、arXiv 编号或文献 URL 批量下载开放获取 PDF，并以（可选 AI 翻译的）中文文件名保存。

## 功能

- 批量输入，每行一个标识（DOI / arXiv ID / arXiv URL / bioRxiv·medRxiv DOI / 开放期刊 DOI）
- 多源解析：arXiv API → bioRxiv/medRxiv API → Crossref + Unpaywall → 着陆页发现
- **bioRxiv / medRxiv 自动下载**：通过系统 Chrome 绕过 Cloudflare 人机挑战（详见下文「bioRxiv 下载说明」）
- **SSE 流式进度** — 逐条返回结果，支持中途取消
- **自动重试** — 网络瞬断指数退避重试（默认 3 次）
- **AI 翻译标题**（可选）— 调用 DeepSeek API 把英文标题译成中文作为文件名
- **环境变量配置** — 端口、邮箱、下载目录、并发数、超时等均可覆盖
- 暗色 Web 前端，默认端口 `7862`

## 安装

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

> bioRxiv / medRxiv 下载额外需要本机已安装 **Google Chrome**（程序通过 Playwright 的 `channel="chrome"` 调用系统 Chrome 来通过 Cloudflare 挑战）。

## 运行

```bash
python app.py
```

打开：**http://127.0.0.1:7862**

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PAPER_PORT` | `7862` | 服务端口 |
| `PAPER_HOST` | `127.0.0.1` | 绑定地址 |
| `PAPER_EMAIL` | `example@example.com` | Unpaywall API 邮箱（建议改成你自己的） |
| `PAPER_DOWNLOAD_DIR` | `./downloads` | PDF 保存目录 |
| `PAPER_MAX_CONCURRENT` | `4` | 并发下载数（bioRxiv 走浏览器时为串行） |
| `PAPER_TASK_TIMEOUT` | `240` | 单篇处理超时（秒）；bioRxiv 浏览器路径较慢，默认放宽 |
| `PAPER_RETRY_MAX` | `3` | 网络重试次数 |
| `PAPER_TIMEOUT` | `30` | 普通 HTTP 请求超时（秒） |
| `PAPER_USER_AGENT` | `paperdownload/0.2 (...)` | 请求 UA（合规 UA 有助于通过部分站点） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek 模型名 |

## AI 翻译标题（可选）

在网页里勾选「AI 翻译标题」并填入 DeepSeek API Key（`sk-…`，保存在浏览器 localStorage）。
翻译仅用于生成中文文件名；不开勾选则用原始英文标题命名，**不需要 API Key**。
DeepSeek 官方模型名为 `deepseek-chat`（通用）或 `deepseek-reasoner`（推理）。

## bioRxiv / medRxiv 下载说明

bioRxiv 与 medRxiv 的 PDF 由 Cloudflare 保护，普通 HTTP 客户端（httpx）会被随机
`403 + "Just a moment…"` 人机挑战拦截。本工具的处理策略：

1. 先用 httpx 直连尝试一次（快路径，对非 Cloudflare 站点零成本）。
2. 若命中 403 / Cloudflare 挑战，自动启动系统 Chrome：
   - 导航到论文着陆页让 Cloudflare 挑战通过；
   - 在页面上下文内 `fetch()` 取回 PDF 二进制并保存。
3. 浏览器进程在服务存活期间复用，并通过 cookie 复用减少重复挑战。

因此下载 bioRxiv 时会**短暂弹出一个 Chrome 窗口**（过挑战必需），随后自动关闭；
单篇约 10–15 秒，批量下载时后续篇章会复用 cookie 而更快。

## 项目结构

```
├── app.py             # FastAPI 入口 + 路由 + 生命周期
├── config.py          # 环境变量配置
├── models.py          # 数据模型
├── utils.py           # HTTP 客户端、正则、辅助函数
├── resolver.py        # 查询检测与文献元数据 / PDF 链接解析
├── downloader.py      # PDF 下载逻辑（httpx + 浏览器 fallback）
├── browser_fetcher.py # Playwright + 系统 Chrome 绕过 Cloudflare
├── translator.py      # DeepSeek API 标题翻译
├── static/            # 前端 (HTML/CSS/JS)
├── downloads/         # 下载的 PDF
└── test_downloader.py # 测试（python test_downloader.py）
```

## 测试

```bash
python test_downloader.py            # 单元测试（无需网络、无需 pytest）
python test_downloader.py --slow     # 额外跑一篇 arXiv 真实下载
```

## 注意

- 只下载公开可访问的预印本或开放获取 PDF，不绕过付费墙或登录限制。
- DeepSeek API Key 存于浏览器 localStorage 并明文传给本地后端；仅适合本地使用，部署到服务器请注意风险。
