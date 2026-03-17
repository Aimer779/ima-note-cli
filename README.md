# ima-note-cli

`ima-note-cli` 是一个基于 Python 的命令行工具，用于通过 IMA OpenAPI 搜索和读取个人笔记。

当前 MVP 支持两个核心流程：

- 检查当前 IMA 凭证是否已配置
- 按标题搜索笔记
- 按 `doc_id` 读取笔记纯文本内容

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

读取指定笔记正文：

```bash
uv run ima-note get "your_doc_id"
```

输出 JSON：

```bash
uv run ima-note search "会议纪要" --json
uv run ima-note get "your_doc_id" --json
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
