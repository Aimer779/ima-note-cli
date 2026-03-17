# ima-note-cli

`ima-note-cli` 是一个基于 Python 的命令行工具，用于通过 IMA OpenAPI 搜索和读取个人笔记。

本项目参考了公开 skill：<https://clawhub.ai/iampennyli/ima-skills>，并结合仓库内的 `skills/ima-note` 实现当前的 IMA 笔记 CLI。

## Features
当前已支持这些能力：

- 检查当前 IMA 凭证是否已配置
- 按标题或正文搜索笔记
- 列出笔记本
- 列出指定笔记本下的笔记
- 按 `doc_id` 读取笔记纯文本内容
- 从 Markdown 新建笔记
- 向已有笔记追加 Markdown 内容

TODO:
- 检索知识库
- 导入知识库

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
ima-note --help
ima-note auth
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

CLI 会按下面顺序读取凭证：

1. 项目根目录的 `.env`
2. 进程环境变量

如果两者同时存在，环境变量优先。

如果你是通过 `uv tool install` 全局安装后在任意目录使用 `ima-note`，推荐直接配置系统环境变量，而不是依赖当前目录下的 `.env`。

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
ima-note auth
```

如果使用 `setx`，需要重新打开终端后再验证。

### Windows terminal encoding

在部分 Windows 终端里，如果默认编码是 `GBK`，而搜索结果标题或摘要里包含 emoji 或其他非 `GBK` 字符，CLI 可能报错：

```text
Error: 'gbk' codec can't encode character ...
```

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
ima-note search "coding"
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

查看帮助：

```bash
ima-note --help
```

检查凭证配置：

```bash
ima-note auth
ima-note auth --json
```

按标题搜索笔记：

```bash
ima-note search "会议纪要"
```

按正文搜索笔记：

```bash
ima-note search "项目排期" --search-type content
```

列出笔记本：

```bash
ima-note folders
ima-note folders --json
```

列出某个笔记本下的笔记：

```bash
ima-note list --folder-id "user_list_xxx"
ima-note list --folder-id "user_list_xxx" --json
```

读取指定笔记正文：

```bash
ima-note get "your_doc_id"
```

新建笔记：

```bash
ima-note create --title "测试标题" --content "正文内容"
ima-note create --file "./note.md" --folder-id "folder_id"
```

追加内容到已有笔记：

```bash
ima-note append "your_doc_id" --content "\n## 补充内容\n\n追加文本"
ima-note append "your_doc_id" --file "./append.md"
```

输出 JSON：

```bash
ima-note search "会议纪要" --json
ima-note folders --json
ima-note list --folder-id "user_list_xxx" --json
ima-note get "your_doc_id" --json
ima-note create --title "测试标题" --content "正文内容" --json
ima-note append "your_doc_id" --content "追加文本" --json
```

如果你是在本地开发，也可以直接运行模块入口：

```bash
uv run python -m ima_note_cli search "会议纪要"
uv run python -m ima_note_cli get "your_doc_id"
```

## Development

运行测试：

```bash
uv run python -m unittest discover -s tests -v
```

如果已经安装为可执行命令，也可以直接运行：

```bash
ima-note search "会议纪要"
ima-note get "your_doc_id"
```

## Project Structure

```text
ima-note-cli/
├── skills/
│   ├── ima-note/
│   │   ├── _meta.json          # 原始 skill 元数据
│   │   ├── SKILL.md            # IMA 笔记能力说明与调用流程
│   │   └── references/
│   │       └── api.md          # IMA 笔记 OpenAPI 参考文档与字段结构
│   └── ima-note-cli/
│       └── SKILL.md            # CLI 安装、验证、配置和使用指南 skill
├── src/
│   └── ima_note_cli/
│       ├── __init__.py         # 包初始化与版本导出
│       ├── __main__.py         # 模块入口，支持 `python -m ima_note_cli`
│       ├── api.py              # IMA API 客户端、响应解析和数据模型
│       ├── cli.py              # argparse 入口、子命令分发和终端输出
│       └── config.py           # `.env` / 环境变量加载与凭证检查
├── tests/
│   ├── test_cli.py             # CLI 命令行为与输出回归测试
│   └── test_config.py          # 配置加载、优先级和缺失场景测试
├── .env                        # 本地开发凭证文件
├── .env.example                # `.env` 模板文件
├── .gitignore                  # Git 忽略规则
├── pyproject.toml              # 项目元数据、构建配置和 CLI 入口定义
├── uv.lock                     # uv 锁文件，固定依赖解析结果
└── README.md                   # 项目说明、安装方式和使用文档
```
