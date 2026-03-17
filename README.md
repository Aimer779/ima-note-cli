# ima-note-cli

`ima-note-cli` 是一个基于 Python 的命令行工具，用于通过 IMA OpenAPI 搜索和读取个人笔记。

本项目参考了公开 skill：<https://clawhub.ai/iampennyli/ima-skills>，并结合仓库内的 `skills/ima-note` 实现当前的 IMA 笔记 CLI。

当前已支持这些能力：

- 检查当前 IMA 凭证是否已配置
- 按标题或正文搜索笔记
- 列出笔记本
- 列出指定笔记本下的笔记
- 按 `doc_id` 读取笔记纯文本内容
- 从 Markdown 新建笔记
- 向已有笔记追加 Markdown 内容

## 安装

推荐使用 `uv`：

```bash
uv venv
uv pip install -e .
```

如果只想临时运行，也可以直接使用 `uv run`，不强依赖全局安装。

如果你更偏好 `pip`：

```bash
pip install -e .
```

## 凭证配置

CLI 会按下面顺序读取凭证：

1. 项目根目录的 `.env`
2. 进程环境变量

如果两者同时存在，环境变量优先。

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

## 用法

查看帮助：

```bash
uv run ima-note --help
```

检查凭证配置：

```bash
uv run ima-note auth
uv run ima-note auth --json
```

按标题搜索笔记：

```bash
uv run ima-note search "会议纪要"
```

按正文搜索笔记：

```bash
uv run ima-note search "项目排期" --search-type content
```

列出笔记本：

```bash
uv run ima-note folders
uv run ima-note folders --json
```

列出某个笔记本下的笔记：

```bash
uv run ima-note list --folder-id "user_list_xxx"
uv run ima-note list --folder-id "user_list_xxx" --json
```

读取指定笔记正文：

```bash
uv run ima-note get "your_doc_id"
```

新建笔记：

```bash
uv run ima-note create --title "测试标题" --content "正文内容"
uv run ima-note create --file "./note.md" --folder-id "folder_id"
```

追加内容到已有笔记：

```bash
uv run ima-note append "your_doc_id" --content "\n## 补充内容\n\n追加文本"
uv run ima-note append "your_doc_id" --file "./append.md"
```

输出 JSON：

```bash
uv run ima-note search "会议纪要" --json
uv run ima-note folders --json
uv run ima-note list --folder-id "user_list_xxx" --json
uv run ima-note get "your_doc_id" --json
uv run ima-note create --title "测试标题" --content "正文内容" --json
uv run ima-note append "your_doc_id" --content "追加文本" --json
```

也可以直接运行模块入口：

```bash
uv run python -m ima_note_cli search "会议纪要"
uv run python -m ima_note_cli get "your_doc_id"
```

## 开发

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
│   └── ima-note/
│       ├── SKILL.md            # Skill 说明，定义支持的笔记能力与调用流程
│       └── references/
│           └── api.md          # IMA 笔记 OpenAPI 参考文档与字段结构
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
└── README.md                   # 项目说明、安装方式和使用文档
```
