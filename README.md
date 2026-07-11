# ima-note-cli

感谢Linux.do社区的支持 https://linux.do/t/topic/1773167
`ima-note-cli` 是一个基于 Python 的命令行工具，用于通过 IMA OpenAPI 管理个人笔记和知识库。

本项目参考了公开 skill：<https://clawhub.ai/iampennyli/ima-skills>，并结合仓库内的参考文档实现当前的 IMA CLI。

## Features
当前已支持这些能力：

- 检查当前 IMA 凭证是否已配置
- 管理笔记：
  - 按标题或正文搜索笔记
  - 列出笔记本
  - 列出指定笔记本下的笔记
  - 按 `note_id` 读取笔记纯文本内容
  - 从 Markdown 新建笔记
  - 向已有笔记追加 Markdown 内容
- 管理知识库：
  - 搜索知识库列表
  - 查看知识库详情
  - 浏览知识库内容
  - 在知识库内搜索文件/文件夹
  - 列出可添加内容的知识库
  - 将已有笔记添加到知识库
  - 导入 URL 到知识库
  - 上传本地文件到知识库
  - 安全查看媒体元数据、读取文本原文并原子导出原文

## Skills

本项目自带两个相关 skill，建议优先从这里开始：

- `skills/ima-note-cli`：用于指导 `ima-note` 的安装、验证、凭证配置和常用命令使用
- `skills/ima-note`：用于提供 IMA 笔记 OpenAPI 的接口能力说明和字段参考

典型分工：

- 需要安装 CLI、排查 `uv tool`、验证 `ima-note auth`：用 `ima-note-cli`
- 需要理解笔记接口、参数、返回结构和工作流：用 `ima-note`


## Installation

如果已经安装了 `uv`，可以直接从 GitHub 安装：

```bash
uv tool install git+https://github.com/Aimer779/ima-note-cli
```

安装完成后即可直接使用：

```bash
ima --help
ima auth
```

更新到最新版本：

```bash
uv tool install --reinstall git+https://github.com/Aimer779/ima-note-cli
```

卸载：

```bash
uv tool uninstall ima-note-cli
```

如果你是在本地开发这个项目，推荐使用：

```bash
git clone https://github.com/Aimer779/ima-note-cli
cd ima-note-cli
uv venv
uv pip install -e .
```

如果只想临时运行仓库代码，也可以直接使用 `uv run`，不强依赖全局安装。

如果你更偏好 `pip`：

```bash
pip install -e .
```

## Credentials Configuration

CLI 按字段独立解析凭证，优先级为：进程环境变量 > 当前工作目录 `.env` > `~/.config/ima/client_id` 或 `~/.config/ima/api_key`。`ima auth` 只显示每个字段是否设置及来源，不显示凭证值。

也可以使用严格 UTF-8 的用户配置文件：

```text
~/.config/ima/client_id
~/.config/ima/api_key
```

如果你是通过 `uv tool install` 全局安装后在任意目录使用 `ima`，推荐直接配置系统环境变量，而不是依赖当前目录下的 `.env`。

### Config ways in different OS

以下两个环境变量是必需的：

```bash
IMA_OPENAPI_CLIENTID=your_client_id
IMA_OPENAPI_APIKEY=your_api_key
```

Windows PowerShell，当前会话临时生效：

```powershell
$env:IMA_OPENAPI_CLIENTID="your_client_id"
$env:IMA_OPENAPI_APIKEY="your_api_key"
```

Windows PowerShell，持久化到当前用户环境变量：

```powershell
setx IMA_OPENAPI_CLIENTID "your_client_id"
setx IMA_OPENAPI_APIKEY "your_api_key"
```

Windows CMD，当前会话临时生效：

```cmd
set IMA_OPENAPI_CLIENTID=your_client_id
set IMA_OPENAPI_APIKEY=your_api_key
```

Windows CMD，持久化到当前用户环境变量：

```cmd
setx IMA_OPENAPI_CLIENTID "your_client_id"
setx IMA_OPENAPI_APIKEY "your_api_key"
```

macOS / Linux（bash / zsh），当前会话临时生效：

```bash
export IMA_OPENAPI_CLIENTID="your_client_id"
export IMA_OPENAPI_APIKEY="your_api_key"
```

macOS / Linux（zsh），持久化到 `~/.zshrc`：

```bash
echo 'export IMA_OPENAPI_CLIENTID="your_client_id"' >> ~/.zshrc
echo 'export IMA_OPENAPI_APIKEY="your_api_key"' >> ~/.zshrc
source ~/.zshrc
```

macOS / Linux（bash），持久化到 `~/.bashrc`：

```bash
echo 'export IMA_OPENAPI_CLIENTID="your_client_id"' >> ~/.bashrc
echo 'export IMA_OPENAPI_APIKEY="your_api_key"' >> ~/.bashrc
source ~/.bashrc
```

fish shell，当前会话临时生效：

```fish
set -x IMA_OPENAPI_CLIENTID "your_client_id"
set -x IMA_OPENAPI_APIKEY "your_api_key"
```

fish shell，持久化：

```fish
set -Ux IMA_OPENAPI_CLIENTID "your_client_id"
set -Ux IMA_OPENAPI_APIKEY "your_api_key"
```

验证配置：

```bash
ima auth
```

如果使用 `setx`，需要重新打开终端后再验证。

### Windows terminal encoding

在部分 Windows 终端里，如果默认编码是 `GBK`，而搜索结果标题或摘要里包含 emoji 或其他非 `GBK` 字符，CLI 可能报错：

```text
Error: 'gbk' codec can't encode character ...
```

从当前版本开始，`ima auth` 会在 Windows 下检查 `PYTHONUTF8` 和 `PYTHONIOENCODING`，如果未正确设置，会直接给出 PowerShell 或 CMD 的修复提示。

推荐按下面顺序处理：

1. 先把终端代码页切到 `UTF-8`
2. 再强制 Python 使用 `UTF-8`

PowerShell：

```powershell
chcp 65001
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

CMD：

```cmd
chcp 65001
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
```

然后重新执行命令：

```bash
ima note search "coding"
```

如果你希望持久化生效，可以在 Windows 里执行：

```powershell
setx PYTHONUTF8 "1"
setx PYTHONIOENCODING "utf-8"
```

执行 `setx` 后需要重新打开终端。

必需字段：

```bash
IMA_OPENAPI_CLIENTID=your_client_id
IMA_OPENAPI_APIKEY=your_api_key
```

仓库中包含：

- `.env.example`：提交到仓库的模板文件
- `.env`：本地开发占位文件

推荐流程：

```bash
cp .env.example .env
```

然后把 `.env` 中的占位值替换为你在 `https://ima.qq.com/agent-interface` 获取到的真实凭证。

示例：

```dotenv
IMA_OPENAPI_CLIENTID=your_client_id
IMA_OPENAPI_APIKEY=your_api_key
```

## Usage

机器调用可在命令末尾增加 `--json`。成功和失败都只输出一个 JSON 文档，公共字段为 `schema_version`、`ok`、`command`、`warnings`；失败时另含稳定的 `error` 对象且 stderr 为空。退出码：输入 2、配置 3、网络 4、IMA 业务 5、协议 6、原文/本地 I/O 7、上传 8、内部错误 70、中断 130。

原文能力：

```bash
ima kb media-info --media-id "media_xxx"
ima kb read --media-id "media_xxx"
ima kb export --media-id "media_xxx" --output "./original.bin"
ima kb export --media-id "media_xxx" --output "./original.bin" --force --json
```

`media-info` 永不显示完整访问 URL 或临时 header 值。`read` 只接受明确文本 MIME 且最大 4 MiB；二进制请使用 `export`。导出以 64 KiB 块处理，最大 200 MiB，默认拒绝覆盖，并通过同目录临时文件和原子替换保护已有文件。媒体 URL 不携带 IMA 长期凭证，临时 header 不允许跨源重定向。用户传给 `add-url` 的 URL 类型探测与“下载再上传”属于后续批次，不是这里的原文读取功能。

查看帮助：

```bash
ima --help
```

检查凭证配置：

```bash
ima auth
ima auth --json
```

笔记命令：

```bash
ima note search "会议纪要"
```

按正文搜索笔记：

```bash
ima note search "项目排期" --search-type content
```

列出笔记本：

```bash
ima note folders
ima note folders --json
```

列出某个笔记本下的笔记：

```bash
ima note list --folder-id "user_list_xxx"
ima note list --folder-id "user_list_xxx" --json
```

读取指定笔记正文：

```bash
ima note get "your_note_id"
```

新建笔记：

```bash
ima note create --title "测试标题" --content "正文内容"
ima note create --file "./note.md" --folder-id "folder_id"
```

追加内容到已有笔记：

```bash
ima note append "your_note_id" --content "\n## 补充内容\n\n追加文本"
ima note append "your_note_id" --file "./append.md"
```

创建和追加会在请求前验证 UTF-8，并移除 Markdown 或 HTML 中的本地图片、data URI 和其他非 HTTP(S) 图片引用；网络图片保留。人类输出会把被移除的路径写到 stderr，`--json` 会在 `warnings` 和 `removed_local_images` 中报告。

知识库命令：

```bash
ima kb search-base "产品文档库"
ima kb show-base --kb-id "kb_xxx"
ima kb browse --kb-id "kb_xxx"
ima kb search "排期" --kb-id "kb_xxx"
ima kb addable
ima kb add-note --kb-id "kb_xxx" --note-id "note_xxx" --title "会议纪要"
ima kb add-url --kb-id "kb_xxx" --url "https://example.com/article"
ima kb add-file --kb-id "kb_xxx" --file "./report.pdf"
```

`--note-id` 是正式参数。`ima kb add-note --doc-id ...` 暂时保留一个兼容周期并会给出弃用提示。Notes 与 add-note 的成功 JSON 以 `note_id` 为正式字段，同时保留值相同的 `doc_id` 兼容字段。

如果你是在本地开发，也可以直接运行模块入口：

```bash
uv run python -m ima_note_cli note search "会议纪要"
uv run python -m ima_note_cli kb search-base "产品文档库"
```

## Development

运行测试：

```bash
uv run python -m unittest discover -s tests -v
```

如果已经安装为可执行命令，也可以直接运行：

```bash
ima note search "会议纪要"
ima kb browse --kb-id "kb_xxx"
```

## Project Structure

```text
ima-note-cli/
├── skills/
│   └── ...
├── src/
│   └── ima_note_cli/
│       ├── __init__.py         # 包初始化与版本导出
│       ├── __main__.py         # 模块入口，支持 `python -m ima_note_cli`
│       ├── api.py              # 兼容导出层
│       ├── cli.py              # 顶层 CLI：`ima auth` / `ima note` / `ima kb`
│       ├── config.py           # `.env` / 环境变量加载与凭证检查
│       ├── http.py             # 共享 HTTP 请求与错误处理
│       ├── notes_api.py        # IMA 笔记 API 客户端与数据模型
│       ├── notes_cli.py        # `ima note ...` 命令实现
│       ├── notes_content.py    # Notes UTF-8 校验与本地图片过滤
│       ├── knowledge_api.py    # IMA 知识库 API 客户端与数据模型
│       ├── knowledge_cli.py    # `ima kb ...` 命令实现
│       └── knowledge_upload.py # 文件预检、COS 签名和上传流程
├── tests/
│   ├── _bootstrap.py           # 为 src 布局测试注入导入路径
│   ├── test_cli.py             # CLI 命令行为与输出回归测试
│   ├── test_config.py          # 配置加载、优先级和缺失场景测试
│   ├── test_http.py            # HTTP wire envelope 契约测试
│   ├── test_notes_api.py       # Notes 1.1.7 endpoint 与解析测试
│   ├── test_notes_content.py   # Markdown 写入安全测试
│   ├── test_knowledge_api.py   # KB add-note note_id 契约测试
│   ├── fixtures/notes/         # 脱敏 Notes 1.1.7 wire fixtures
│   └── test_knowledge_upload.py# 知识库上传预检与签名测试
├── .env                        # 本地开发凭证文件
├── .env.example                # `.env` 模板文件
├── .gitignore                  # Git 忽略规则
├── pyproject.toml              # 项目元数据、构建配置和 CLI 入口定义
├── uv.lock                     # uv 锁文件，固定依赖解析结果
└── README.md                   # 项目说明、安装方式和使用文档
```
