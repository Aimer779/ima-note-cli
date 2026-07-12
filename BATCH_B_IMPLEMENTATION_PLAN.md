# 批次 B 详细实现计划：公共基础与原文能力

> 阶段 6 注：当时的 intake 路径 `ima-skills-1.1.7 (1)` 已按原始 bytes 归档为 `third_party/ima-skills/1.1.7/original`；下文旧路径只表示历史基线。当前唯一规范契约为 `docs/IMA_OPENAPI_CONTRACT_1_1_7.md`。

> 编制日期：2026-07-11  
> 对应总计划：`OPTIMIZATION_PLAN.md` 的阶段 2，以及阶段 3 中的 `get_media_info`、原文读取/导出和 Notes 跨模块读取  
> 实施基线：批次 A 已实施，`uv run python -m unittest discover -s tests -v` 为 66/66 通过  
> 计划状态：已实施（离线测试与对抗性评审通过）  
> 生产依赖策略：不新增生产依赖，继续仅使用 Python 标准库

## 1. 批次目标

批次 B 同时解决两组相互依赖的问题：

1. 共享 HTTP、配置、错误和机器输出缺少稳定、安全的公共基础。
2. 知识库缺少 `get_media_info`、原文查看/导出，以及 `media_type=11` 时转调 Notes 的完整能力。

完成后，项目应具备可预测的错误类型和退出码、稳定且不混入人类文本的 JSON 输出、有限且只用于安全读取的重试、严格的响应字段校验、三层凭证来源、固定的官方域名安全边界，以及以下原文命令：

```text
ima kb media-info --media-id MEDIA_ID
ima kb read --media-id MEDIA_ID
ima kb export --media-id MEDIA_ID --output PATH
```

其中：

- 笔记类型媒体通过 Knowledge `get_media_info` 获取 `note_id`，再调用 Notes `get_doc_content`；
- URL 类型媒体只消费 IMA `get_media_info` 返回的受控访问地址和临时请求头；
- 用户直接传给 `ima kb add-url` 的 URL 探测、文件型 URL 下载再上传不在本批次，继续由批次 C 处理。

## 2. 范围边界

### 2.1 本批次包含

- 建立统一的 CLI 错误基类、错误子类、机器错误码和进程退出码；
- 保留 `ApiError`、`ConfigError`、`KnowledgeUploadError` 的兼容导入路径；
- 为所有 `--json` 命令增加稳定的公共成功/失败字段；
- 让 JSON 失败只写 stdout，stderr 保持为空；
- 收紧 IMA 响应 envelope、嵌套字段、关键 ID、布尔值和数值解析；
- 为 IMA 成功响应、HTTP 错误响应和媒体正文分别设置大小上限；
- 对安全的读取接口执行有限退避重试；
- 明确禁止对创建、追加、导入、上传等写操作自动重试；
- 加入 `~/.config/ima/client_id` 和 `~/.config/ima/api_key`；
- 固化环境变量、项目 `.env`、用户配置文件的优先级；
- 单次命令只解析一次 `.env` 和用户配置；
- `ima auth` 报告每个字段的来源，但绝不显示值；
- 将 IMA 长期凭证限制在 `https://ima.qq.com`；
- 校验 COS 目标必须为合法的 `*.myqcloud.com` HTTPS 地址；
- 校验媒体原文 URL、临时请求头和重定向边界；
- 增加 CLI 版本化 `User-Agent` 和 `Accept: application/json`；
- 建立 Knowledge 1.1.7 脱敏 wire fixtures；
- 实现 `get_media_info` 数据模型和 API 方法；
- 增加 `media-info`、`read`、`export` 命令；
- 实现 `media_type=11` 到 Notes `get_doc_content` 的跨模块编排；
- 对文本型 URL 原文提供受限读取；
- 对二进制 URL 原文提供流式导出，不把二进制写到终端；
- 导出默认拒绝覆盖、失败清理临时文件、成功后原子替换；
- 补齐现有 Knowledge API 的数量上限、分页上限和关键字段测试；
- 更新 README、活动 CLI skill 和契约文档。

### 2.2 本批次不包含

- 对用户输入 URL 执行 HEAD、MIME、`Content-Disposition` 和文件扩展名探测；
- 将用户输入的文件型 URL 下载到临时目录后走上传流程；
- Bilibili、YouTube 等 URL 分类规则的全面重构；
- COS 大文件流式上传、上传前后文件状态复核；
- `--on-conflict error|rename` 和批量文件上传；
- COS 凭证有效期、音频时长和孤立 media 补偿的完整实现；
- CLI `commands/`、`services/`、`models/` 目录的全面拆分；
- 移除 `doc_id` 兼容层；
- 合并或删除现有 skills 目录；
- CI、lint、类型检查、coverage 和发布流水线；
- 任意 `IMA_BASE_URL` 或非官方 IMA API 代理；
- Node.js/CJS 运行时、自更新或命令行传递长期凭证；
- 真实账户写入 smoke test。

本批次允许修改 `knowledge_upload.py` 的错误基类和 COS 域名防护，但不借此提前实施批次 C 的上传服务重构。

## 3. 当前问题

### 3.1 错误类型和退出码无法区分

当前顶层 `cli.py` 统一捕获：

- `ConfigError`；
- `ApiError`；
- `KnowledgeUploadError`；
- `ValueError`。

无论是参数错误、凭证缺失、网络超时、后端业务错误、协议漂移还是上传失败，最终都打印 `Error: ...` 并返回 1。

这会造成：

- 自动化无法判断是否应修正参数、重新认证或稍后重试；
- `ValueError` 同时承担用户输入错误和潜在程序缺陷；
- API 协议错误和后端业务拒绝无法区分；
- 上传和本地文件错误没有稳定机器标识；
- 后续命令只能继续增加临时的 `except` 分支。

### 3.2 JSON 模式只覆盖成功输出

当前成功命令能输出 JSON，但异常始终是 stderr 上的人类文本：

```text
Error: boom
```

因此调用方不能只解析 stdout 获得完整结果，也无法稳定识别错误类型。参数解析失败仍由 argparse 输出 usage 文本，和 API 失败的格式完全不同。

同时，各成功 JSON 没有统一的：

- Schema 版本；
- 成功/失败判别字段；
- 命令标识；
- warnings 字段；
- 错误对象。

### 3.3 HTTP 读取没有大小边界

当前 `http.py` 对成功响应直接调用 `response.read()`，对 `HTTPError` 也读取完整正文。

风险包括：

- 异常服务端可返回超大正文并消耗内存；
- HTML 网关错误页可能被完整拼入异常；
- 错误正文可能含签名 URL、Authorization、Cookie 或服务端内部信息；
- 非 JSON 和错误 Content-Type 无法提供安全、有限的诊断；
- 后续原文导出若复用该逻辑，会进一步放大内存风险。

### 3.4 HTTP 错误摘要可能泄露敏感内容

`_read_error_body` 当前把服务端正文直接解码并拼入错误消息。未来 `get_media_info` 返回的 URL 查询参数和 headers 也可能包含短期访问凭证。

必须确保：

- IMA Client ID 和 API Key 永远不出现在异常、JSON、repr 或测试快照；
- Authorization、Cookie、签名查询参数只在实际请求内部使用；
- HTTP 错误只提取有限、已清洗的 `msg` 或 `message`；
- 非 JSON 错误只报告状态码、endpoint 和安全原因，不回显正文。

### 3.5 没有安全读取重试

所有网络错误当前立即失败。短暂的连接中断、HTTP 429、502、503、504 会直接终止只读命令。

但简单地为所有 POST 增加重试也不安全，因为 IMA 的读取和写入都使用 POST：

- `search_note`、`get_media_info` 是安全读取；
- `import_doc`、`append_doc`、`add_knowledge`、`create_media` 可能产生不可逆副作用。

重试策略必须由调用点显式声明，而不能依据 HTTP method 判断。

### 3.6 顶层 envelope 已收紧，嵌套字段仍然宽松

批次 A 已要求顶层 `code` 和对象型 `data`，但 Knowledge 解析仍大量使用：

- `str(value)`；
- `bool(value)`；
- `data.get("items", [])`；
- 错误类型时返回空列表或空对象；
- 缺少关键 ID 时继续构造成功模型。

具体风险：

- `str(None)` 变成字符串 `"None"`；
- `bool("false")` 和 `bool("0")` 都是 `True`；
- `info_list: null` 被当作空结果；
- `media_id` 缺失时 CLI 仍可能显示成功；
- 错误的 `headers` 结构可能在下载阶段才暴露；
- 协议漂移被吞掉，无法通过测试及时发现。

### 3.7 凭证来源不完整且会重复读取

当前只支持：

1. 进程环境变量；
2. 当前工作目录 `.env`。

缺少 1.1.7 推荐的：

- `~/.config/ima/client_id`；
- `~/.config/ima/api_key`。

顶层命令先调用 `inspect_credentials`，随后非 `auth` 命令又调用 `load_credentials`，导致同一 `.env` 在一个命令内解析两次。若文件恰好在两次读取之间变化，状态和实际凭证甚至可能不一致。

### 3.8 长期凭证的目标域名边界没有在公共层强制

Notes 和 Knowledge 客户端当前传入固定 Base URL，但 `ImaApiClient` 构造函数接受任意 `base_url`。测试也使用 `https://example.com/api`。

这意味着未来调用方或重构代码可能把长期凭证发送到非官方域名。仅依赖“当前调用方没有这样做”不足以构成安全边界。

COS 上传也直接拼接：

```text
{bucket_name}.cos.{region}.myqcloud.com
```

如果 `bucket_name` 或 `region` 包含 `@`、斜杠、端口等字符，URL authority 可能被改变。必须在构造 Request 前验证。

### 3.9 缺少 get_media_info 契约和模型

1.1.7 定义：

```text
POST /openapi/wiki/v1/get_media_info
{"media_id": "..."}
```

返回有三个合法分支：

1. 非笔记媒体：`url_info.url` 和可选 `url_info.headers`；
2. 笔记媒体：`media_type=11` 和 `notebook_ext_info.notebook_id`；
3. 暂不可访问：有 `media_type`，但没有可用 `url_info`。

当前 `knowledge_api.py` 没有 endpoint、模型、校验和测试。

### 3.10 当前 CLI 无法完成跨模块读取

`cli.py` 对 `kb` 命令只构造 `KnowledgeBaseApiClient`，`knowledge_cli.py` 的 handler 也只接受 Knowledge client。

笔记型媒体需要：

```text
KnowledgeBaseApiClient.get_media_info(media_id)
  -> media_type == 11
  -> notebook_ext_info.notebook_id
  -> NotesApiClient.get_doc_content(note_id)
```

若直接在 `knowledge_api.py` 内部创建 Notes client，会造成客户端互相耦合、测试难以注入，也会让 API 层承担命令编排责任。

### 3.11 原文 URL 和临时 headers 有新的泄露风险

`get_media_info` 可能返回：

- 带签名查询参数的 URL；
- Authorization 等短期 header；
- 需要重定向的下载地址。

Python urllib 默认重定向行为不应被直接信任，因为跨域重定向可能把临时 header 带到另一个 host。原文能力必须独立于 IMA 长期凭证，并对 scheme、host、重定向、header、大小和输出做限制。

### 3.12 Knowledge 接口上限没有统一落实

当前只完整校验了部分下限和 URL 数量：

- `search_knowledge_base.limit` 应为 1–20；
- `get_knowledge_list.limit` 应为 1–50；
- `get_addable_knowledge_base_list.limit` 应为 1–50；
- `get_knowledge_base.ids` 应为 1–20 且不重复；
- `import_urls.urls` 应为 1–10；
- `check_repeated_names.params` 应为 1–2000。

CLI 和 Python API 都必须校验，不能只依赖 argparse 或服务端。

## 4. 实现原则和已选策略

### 4.1 保持标准库实现和兼容入口

本批次不新增生产依赖。继续使用：

- `urllib.request`；
- `urllib.parse`；
- `json`；
- `dataclasses`；
- `pathlib`；
- `hashlib`；
- `time`；
- `typing`。

保留：

- `ima` 和 `ima-note` 两个入口；
- `ApiError` 公共导出；
- `ConfigError` 从 `ima_note_cli.config` 导入；
- `KnowledgeUploadError` 从 `ima_note_cli.knowledge_upload` 导入；
- 批次 A 的 `note_id`/`doc_id` 兼容行为；
- 现有成功 JSON 的命令专属字段路径。

### 4.2 统一错误层级

新增 `src/ima_note_cli/errors.py`，建议层级：

```text
ImaCliError
├── InputError
├── ConfigError
├── ApiError
│   ├── ApiTransportError
│   ├── ApiBusinessError
│   └── ApiProtocolError
├── MediaUnavailableError
├── LocalIOError
└── KnowledgeUploadError
```

每个错误至少携带：

- `code`：稳定的小写蛇形机器码；
- `message`：经过清洗、可展示的信息；
- `exit_code`：稳定进程退出码；
- `retryable`：调用方能否稍后重试；
- `endpoint`：仅在安全时包含 endpoint 名，不包含完整 URL；
- `details`：只允许白名单字段，如 `attempts`、`http_status`、`limit`。

禁止把以下内容放入错误对象：

- Client ID；
- API Key；
- Authorization/Cookie 值；
- COS Secret ID/Secret Key/token；
- 完整签名 URL；
- 原始响应正文；
- 本地凭证文件内容。

### 4.3 固定退出码

| 退出码 | 类别 | 示例 |
| --- | --- | --- |
| 0 | 成功 | 查询、读取、导出成功 |
| 2 | 输入/usage | 非法 limit、空 ID、目标文件已存在 |
| 3 | 配置/认证前置 | 缺少凭证、凭证文件不可读 |
| 4 | 网络/超时 | DNS、连接、超时、重试耗尽 |
| 5 | IMA 业务错误 | `code != 0` |
| 6 | API 协议错误 | 缺字段、错误类型、超大/非法 JSON |
| 7 | 原文或本地 I/O | 原文不可访问、二进制不能 read、导出写入失败 |
| 8 | 上传错误 | COS 上传失败 |
| 70 | 未预期内部错误 | 不回显底层异常文本 |
| 130 | 用户中断 | `KeyboardInterrupt` |

`ima auth` 在缺少凭证时返回 3，而不是当前的 1。此变化需写入 README；只判断“是否非零”的现有脚本仍兼容。

### 4.4 JSON 使用扁平兼容 envelope

为避免破坏批次 A 已有字段路径，不把命令结果整体移动到 `data` 下。所有成功 JSON 在原字段基础上增加：

```json
{
  "schema_version": 1,
  "ok": true,
  "command": "note.search",
  "warnings": [],
  "query": "会议",
  "docs": []
}
```

所有失败 JSON 使用：

```json
{
  "schema_version": 1,
  "ok": false,
  "command": "kb.read",
  "warnings": [],
  "error": {
    "code": "media_unavailable",
    "message": "The original content is not available through the API.",
    "exit_code": 7,
    "retryable": false,
    "endpoint": "get_media_info"
  }
}
```

规则：

- JSON 模式下，无论成功失败，机器结果只写 stdout；
- JSON 模式失败时 stderr 必须为空；
- 人类模式错误只写 stderr；
- `warnings` 始终存在且为数组；
- `error` 只在 `ok=false` 时存在；
- `command` 使用稳定的点分名称，如 `kb.media-info`；
- argparse usage 错误也转为同一错误对象；
- `--help` 保持标准帮助文本，不视为 JSON 业务结果；
- 未预期异常只返回通用 `internal_error`，不回显异常字符串。

### 4.5 凭证优先级

按字段分别解析，优先级固定为：

```text
进程环境变量
  > 当前工作目录 .env
  > ~/.config/ima/client_id 或 ~/.config/ima/api_key
```

选择该顺序的原因：

- 环境变量继续拥有最高、最显式的覆盖权；
- 保持现有项目 `.env` 相对用户全局配置的行为；
- 用户配置为全局安装和任意工作目录提供回退；
- 保留当前允许 Client ID 与 API Key 来自不同层的兼容行为。

`ima auth` 只输出来源标签：

- `environment`；
- `project_dotenv`；
- `user_config`；
- `missing`。

若展示路径，用户目录必须缩写为 `~/.config/ima/...`；不得打印绝对 home 路径或任何值。

### 4.6 单次配置快照

新增不可变的配置解析结果，例如 `CredentialResolution`：

- 一次读取环境、`.env` 和两个用户配置文件；
- 同时产生 `CredentialStatus` 和可用 `Credentials`；
- `run` 不再先 inspect、再二次 load；
- 兼容函数 `inspect_credentials` 和 `load_credentials` 内部委托给同一解析函数；
- 测试可注入 cwd、home/config_dir 和环境映射，不修改真实用户目录。

### 4.7 IMA、COS 和媒体 URL 安全边界

IMA 长期凭证：

- 只允许 scheme `https`；
- hostname 必须精确为 `ima.qq.com`；
- 禁止 userinfo、非默认端口、query 和 fragment；
- service path 只允许已知的 `/openapi/note/v1` 与 `/openapi/wiki/v1`；
- endpoint 必须是受限的相对名称；
- 不提供生产可用的 `allow_insecure` 或任意 Base URL 开关。

COS 临时凭证：

- `bucket_name` 和 `region` 必须匹配受限 DNS label；
- 构造后的 hostname 必须以标签边界匹配 `.myqcloud.com`；
- 禁止 userinfo、端口、反斜杠、控制字符和 authority 注入；
- 继续忽略任意 `custom_domain`，本批次不向自定义域发送 COS 凭证；
- 完整 COS key 规范化和凭证有效期校验仍在批次 C。

`get_media_info` 原文 URL：

- 初始只允许 HTTPS；
- 按 1.1.7 skill 的允许域，首批仅允许 `ima.qq.com` 和合法 `*.myqcloud.com`；
- 若真实只读 smoke 发现新的官方 CDN，先补契约 fixture 和显式 allowlist，再支持；
- 禁止 IP literal、localhost、userinfo、非默认端口、`file://`；
- 临时 headers 只用于该原文请求，绝不混入 IMA 长期 headers；
- 有临时 headers 时只允许同源重定向；
- 跨源重定向直接失败，不尝试转发或静默剥离后继续；
- URL query、header values 和完整 URL 不进入日志、JSON 或异常。

### 4.8 HTTP 大小限制和安全摘要

建议常量：

| 内容 | 上限 | 行为 |
| --- | --- | --- |
| IMA JSON 成功响应 | 4 MiB | 读取 `limit + 1`，超限报协议错误 |
| HTTP 错误正文 | 16 KiB | 只尝试提取 JSON `msg/message` |
| 可展示错误摘要 | 512 字符 | 去控制字符、折叠空白、执行敏感字段清洗 |
| `kb read` URL 文本 | 4 MiB | 超限提示改用 export |
| `kb export` 原文 | 200 MiB | 流式计数，超限删除临时文件 |

若 Content-Length 已超过上限，应在读取前失败；若缺少或不可信，读取时仍按实际字节数强制限制。

### 4.9 有限重试策略

读取接口显式调用 `post_read_json`，写入接口显式调用 `post_write_json`。

安全读取最多 3 次尝试：

```text
第 1 次失败 -> 等待 0.25 秒
第 2 次失败 -> 等待 0.50 秒
第 3 次失败 -> 返回 ApiTransportError
```

可重试：

- `TimeoutError`；
- 临时 `URLError`；
- HTTP 408、429、500、502、503、504。

不重试：

- IMA `code != 0` 业务错误；
- JSON/协议错误；
- HTTP 400、401、403、404、409 等非临时错误；
- `import_doc`、`append_doc`；
- `add_knowledge`、`import_urls`、`create_media`；
- COS PUT。

`Retry-After` 仅接受有限整数秒，最大等待 2 秒。sleep 函数必须可注入，测试不真实等待。

### 4.10 严格协议解析

新增 `protocol.py`，提供带字段路径的解析器：

- `require_object` / `optional_object`；
- `require_array` / `optional_array`；
- `require_string` / `optional_string`；
- `require_non_empty_string`；
- `require_int` / `optional_int`，拒绝 bool；
- `require_bool`，不使用 Python truthiness；
- `require_string_map`，校验 header 名和值；
- `require_identifier`；
- `require_pagination`。

约定：

- 只有契约明确可选的字段才能缺失或为 null；
- 必填集合缺失或类型错误时不得降级为空集合；
- 布尔字段只接受 JSON true/false；
- 整数允许 JSON integer；若需兼容 int64 字符串，只接受规范十进制字符串并写入契约裁决；
- 任何错误都包含 endpoint 和字段路径，如 `get_media_info.data.media_type`；
- 错误不包含字段值，避免敏感数据泄漏。

### 4.11 get_media_info 模型

新增冻结模型：

```text
MediaAccessInfo
  - url
  - headers（repr=False，不直接序列化）
  - safe_host
  - header_names

MediaInfo
  - media_id
  - media_type
  - source_kind: note | url | unavailable
  - note_id
  - access: MediaAccessInfo | None
```

分支规则：

- `media_type == 11` 时必须存在非空 `notebook_ext_info.notebook_id`；
- 笔记分支统一映射为内部 `note_id`；
- 非 11 且 `url_info` 存在时，`url` 必须非空且 headers 必须为字符串映射；
- 非 11 且无 `url_info` 是合法的 `unavailable` 元数据结果；
- 同时出现互相冲突的 note/url 分支时返回协议错误，不猜测优先级；
- `media-info` 的安全输出不包含完整 URL、query 或 header values。

### 4.12 原文读取和导出策略

新增 `MediaContentService`，只负责编排，不持有长期凭证文本。

笔记分支：

1. Knowledge `get_media_info`；
2. 校验 `media_type=11` 和 `note_id`；
3. Notes `get_doc_content(note_id)`；
4. `read` 返回文本；
5. `export` 以严格 UTF-8 字节写入用户指定文件。

URL 分支：

1. Knowledge `get_media_info`；
2. 安全校验 URL 和临时 headers；
3. 使用独立、不含 IMA 长期 headers 的 GET 客户端；
4. `read` 只接受明确文本 MIME 且不超过 4 MiB；
5. 二进制或未知 MIME 提示使用 `export`；
6. `export` 以 64 KiB 块流式写入同目录临时文件；
7. 计算 SHA-256 和实际字节数；
8. 成功后原子替换为目标文件；
9. 任何失败都关闭响应并删除临时文件。

导出规则：

- `--output` 必填，避免从不可信 URL 推导文件名；
- 默认拒绝覆盖已存在文件；
- `--force` 才允许替换；
- 目标为目录、符号链接策略异常或父目录不存在时明确失败；
- JSON 只返回目标路径、字节数、SHA-256、content type 和 source kind；
- 不返回临时路径、签名 URL 或 headers。

### 4.13 CLI 依赖注入

不让 `KnowledgeBaseApiClient` 直接创建 `NotesApiClient`。

调整为：

```text
cli.run
  -> 构造同一份 Credentials
  -> 构造 KnowledgeBaseApiClient
  -> 仅媒体 read/export 时构造 NotesApiClient + MediaContentService
  -> knowledge_cli 负责薄分发和输出
```

测试使用 Fake Knowledge、Fake Notes 和 Fake Source Client，分别验证：

- Knowledge 元数据失败后不调用 Notes；
- 非 11 分支不调用 Notes；
- 11 分支不调用 URL 客户端；
- URL 分支不调用 Notes；
- unavailable 分支不发第二个请求。

## 5. 详细实施步骤

### B0.1 建立 Knowledge/Media 契约裁决文档

新增 `docs/KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md`。

至少记录：

- `get_media_info` endpoint 和请求体；
- 三种合法响应分支；
- `notebook_id -> note_id` 映射；
- URL 和 headers 的敏感性；
- 安全序列化字段；
- 允许域和重定向策略；
- 原文读取/导出上限；
- Knowledge 现有接口的 required/optional 字段；
- 数量上限；
- 待真实只读 smoke 验证项。

待验证项至少包括：

1. 实际 URL host 是否只有 IMA/COS；
2. URL 响应是否稳定包含 Content-Type/Length；
3. 笔记分支是否可能同时返回 `url_info`；
4. 不可访问媒体是否可能返回空对象型 `url_info`；
5. headers 是否只包含 Authorization，或可能包含其他必需字段；
6. URL 是否会跨 host 重定向。

### B0.2 建立 Knowledge wire fixtures

新增 `tests/fixtures/knowledge/README.md`，规定：

- 不得复制真实账户响应；
- 使用 `kb_test_*`、`media_test_*`、`note_test_*`；
- 时间固定；
- URL 使用允许域下的虚构路径；
- Authorization 只用明确的 fixture 占位值；
- 不包含真实签名、Cookie、正文或文件。

至少增加：

```text
search_knowledge_base_success.json
get_knowledge_base_success.json
get_knowledge_list_mixed_success.json
search_knowledge_success.json
get_addable_knowledge_base_list_success.json
check_repeated_names_success.json
import_urls_partial_success.json
create_media_success.json
add_knowledge_success.json
get_media_info_url_success.json
get_media_info_note_success.json
get_media_info_unavailable_success.json
get_media_info_missing_media_type.json
get_media_info_invalid_headers.json
get_media_info_business_error.json
```

fixture 必须包含完整 `code/msg/data` envelope。

### B0.3 扩展 fixture 加载辅助

修改 `tests/_fixtures.py`：

- 支持 Knowledge fixture 路径；
- 路径必须保持在 `tests/fixtures` 下；
- 只用 UTF-8 读取；
- 非对象顶层 fixture 立即使测试失败；
- 不在 loader 中进行生产协议容错。

### B1.1 新增统一错误模块

新增 `src/ima_note_cli/errors.py`：

- 实现错误层级和退出码常量/枚举；
- 对 `message`、`endpoint`、`details` 做安全规范化；
- 提供 `to_error_dict()`；
- 禁止把任意异常 `repr` 自动放入 details；
- 为兼容 `ApiError("message")` 提供默认业务错误语义；
- 为每个子类定义稳定 code、exit code 和 retryable 默认值。

修改 `config.py`、`http.py`、`knowledge_upload.py` 以重新导出兼容名称。

### B1.2 新增公共 JSON/错误输出

新增 `src/ima_note_cli/output.py`：

- `emit_json_success(command, payload, warnings=())`；
- `emit_json_error(command, error)`；
- `emit_human_error(error)`；
- 固定 `schema_version=1`；
- 检测 payload 不得覆盖 `schema_version`、`ok`、`command`、`error`；
- 合并已有 Notes warnings，保持顺序和去重策略明确；
- 使用 `ensure_ascii=False`；
- 所有输出以单个合法 JSON 文档结束。

修改 `notes_cli.py`、`knowledge_cli.py` 和 `cli.py`，移除各处直接的 `json.dumps`。

### B1.3 让 argparse 错误进入统一出口

在 `cli.py` 增加自定义 ArgumentParser 或等价异常桥接：

- parser error 转为 `InputError`；
- 保持 argparse 的退出码语义为 2；
- 在 parse 前从 argv 检测 `--json`，以便参数不完整时仍输出 JSON 错误；
- `--help` 和版本帮助保持标准行为；
- 不捕获并误包装正常的 help `SystemExit(0)`；
- 命令路径无法确定时使用 `command="cli"`。

### B1.4 重构配置解析为单次快照

修改 `config.py`：

- 增加用户配置目录解析；
- 增加单次 `resolve_credentials`；
- 对每个来源只读取一次；
- 对用户配置文件使用严格 UTF-8；
- 空文件、纯空白视为未配置；
- 无权限、目录冒充文件、非法 UTF-8 转为 `ConfigError`；
- 不把原始 OS 错误中的敏感路径和值直接回显；
- 保持 `parse_dotenv` 公共函数；
- 保持现有字段级混合来源行为；
- `load_credentials` 可接受已解析状态，避免二次读取。

修改 `cli.py`：

- 单次命令只调用一次 resolver；
- `auth` 和实际 client 使用同一快照；
- JSON/human auth 都报告安全来源；
- 缺少凭证时返回配置退出码 3。

### B1.5 新增 URL/域名安全工具

新增 `src/ima_note_cli/security.py`：

- `validate_ima_base_url`；
- `validate_relative_endpoint`；
- `build_and_validate_cos_origin`；
- `validate_media_source_url`；
- `sanitize_header_map`；
- `redact_sensitive_text`；
- `safe_url_host`。

安全函数必须：

- 使用 `urlsplit` 后逐字段检查；
- 用 hostname 标签边界判断，不用简单 `endswith("myqcloud.com")`；
- 拒绝控制字符和 CRLF；
- header 名符合 HTTP token 规则；
- 拒绝 `Host`、`Content-Length`、`Transfer-Encoding` 等由客户端控制的 header；
- 允许契约需要的 Authorization，但标记为敏感且禁止序列化；
- 错误只报告策略原因，不报告完整 URL/header。

### B1.6 全面加固 IMA HTTP 层

修改 `http.py`：

- 生产 client 只接受已验证的官方 service URL；
- 请求增加版本化 User-Agent 和 Accept；
- 区分 `post_read_json` 与 `post_write_json`；
- 读取成功正文时执行 4 MiB 上限；
- 读取 HTTP error 时执行 16 KiB 上限；
- 错误摘要最大 512 字符并执行 redaction；
- 区分 Transport、Business、Protocol 错误；
- 对 read 执行 3 次有限重试；
- write 永不自动重试；
- sleep/opener 可测试注入；
- 将 attempts 和 HTTP status 作为白名单 details；
- 非 UTF-8、非 JSON、非对象、缺 code/data 继续作为协议错误；
- success code 只接受整数 0 或兼容字符串 `"0"`，拒绝 bool。

### B1.7 增加 HTTP 安全与重试测试

扩展 `tests/test_http.py`，覆盖：

- User-Agent 包含包版本；
- Accept 和凭证 headers 正确；
- 非官方 Base URL 在构造或请求前被拒绝；
- endpoint authority 注入被拒绝；
- 成功响应刚好等于上限；
- 成功响应超过上限 1 字节；
- HTTP error 只读取有限字节；
- JSON msg 会被安全提取；
- HTML/raw body 不会回显；
- Authorization、API Key、签名 query 被清洗；
- read 在 timeout/503 后按 0.25、0.50 重试；
- 429 的受限 Retry-After；
- business/protocol error 不重试；
- write timeout 只调用一次；
- 重试耗尽返回 retryable Transport error；
- 所有测试 mock 网络且不 sleep。

### B1.8 新增严格协议解析器

新增 `src/ima_note_cli/protocol.py` 和 `tests/test_protocol.py`。

测试矩阵：

- object/array/string/int/bool 正常值；
- 缺字段；
- null；
- bool 被错误当 int；
- `"false"` 不得当 true；
- `None` 不得变成 `"None"`；
- header 非对象、非字符串键值、CRLF；
- 字段路径稳定；
- 错误消息不包含字段原值。

### B1.9 迁移 Notes 和 Knowledge 解析

修改 `notes_api.py`：

- 将现有局部解析辅助迁移到共享 protocol；
- 保持批次 A endpoint/payload/模型和 `doc_id` 兼容不变；
- 所有关键字段缺失继续失败；
- 为读取调用显式使用 `post_read_json`；
- 创建/追加使用 `post_write_json`。

修改 `knowledge_api.py`：

- 替换所有 `str(None)`、`bool(value)` 和静默空集合；
- 对集合字段、分页字段、条目类型和关键 ID 严格校验；
- read/write endpoint 明确分类；
- `add_knowledge` 和 `create_media` 缺 `media_id` 时失败；
- `check_repeated_names.is_repeated` 只接受 bool；
- `import_urls.ret_code=0` 时必须有非空 `media_id`；
- partial failure 仍保留为合法业务结果，供批次 C 处理整体退出语义。

### B1.10 落实输入数量上限

在 Python API 和 CLI 两层校验：

| 接口 | 限制 |
| --- | --- |
| `search_knowledge_base` | limit 1–20 |
| `get_knowledge_list` | limit 1–50 |
| `get_addable_knowledge_base_list` | limit 1–50 |
| `get_knowledge_base` | 1–20 个非空、唯一 ID |
| `import_urls` | 1–10 个 URL |
| `check_repeated_names` | 1–2000 个参数 |
| Notes search/list | 延续批次 A 的 1–20 |

所有无效输入必须在网络调用前失败，并返回 `InputError`。

### B1.11 加固 COS 目标域名

修改 `knowledge_upload.py`：

- 在构造签名和 Request 前验证 bucket/region/host；
- Request URL 必须重新解析并确认 hostname；
- COS 错误正文也使用有限读取和安全摘要；
- `KnowledgeUploadError` 接入统一错误层；
- 保持当前 PUT 数据和 Gate 顺序不变；
- 不在本批次改为流式上传；
- 不自动重试 PUT。

扩展 `tests/test_knowledge_upload.py`：

- 合法 COS host；
- bucket/region 含 `@`、斜杠、端口、控制字符；
- 非 `myqcloud.com` 目标；
- error body 超限和敏感信息清洗；
- 失败后现有 add_knowledge 停止不变量仍通过。

### B2.1 实现 get_media_info API

修改 `knowledge_api.py`：

- 增加 `MediaAccessInfo` 和 `MediaInfo`；
- 增加 `get_media_info(media_id)`；
- 空/非字符串 media_id 在请求前拒绝；
- endpoint 固定 `get_media_info`；
- 使用安全读取重试；
- 严格解析 media_type；
- 实现 note/url/unavailable 三分支；
- headers 在模型 repr 中隐藏；
- 提供单独的安全序列化函数或属性。

扩展 `tests/test_knowledge_api.py`：

- endpoint 和 payload；
- URL 分支；
- Notes 分支和 notebook_id 映射；
- unavailable 分支；
- 缺 media_type；
- media_type bool/字符串错误；
- 无 note ID；
- URL/header 错误类型；
- 冲突分支；
- 业务错误；
- 模型 repr 不含 header value。

### B2.2 实现安全原文 HTTP 客户端

新增 `src/ima_note_cli/source_http.py`：

- 不接受 `Credentials`；
- 只接收经过校验的 `MediaAccessInfo`；
- 创建独立 GET Request；
- 实现受限 RedirectHandler；
- 不向跨源 redirect 发送临时 headers；
- 支持文本读取上限；
- 支持流式导出上限；
- 校验 Content-Length 和实际字节；
- 解析 Content-Type 时不执行危险猜测；
- 对文本使用声明 charset；缺省时严格 UTF-8；
- 不用 `errors="ignore"` 或 `errors="replace"` 隐藏正文编码问题；
- 返回安全元数据，不返回 URL/header。

### B2.3 实现跨模块媒体服务

新增 `src/ima_note_cli/media_service.py`：

- 注入 Knowledge client、Notes client 和 Source client；
- 增加 `inspect_media`；
- 增加 `read_media`；
- 增加 `export_media`；
- 笔记、URL、unavailable 分支互斥；
- 导出使用同目录临时文件和原子替换；
- 默认拒绝覆盖；
- `--force` 时也先完整写好临时文件再替换；
- 计算 SHA-256；
- 失败清理临时文件；
- 输出模型不包含敏感访问数据。

### B2.4 增加媒体服务测试

新增 `tests/test_source_http.py`：

- URL 请求不含 IMA Client ID/API Key；
- 返回临时 Authorization 只发往初始同源；
- 同源重定向可继续；
- 跨源重定向拒绝且不发第二次敏感请求；
- 非 HTTPS、IP literal、localhost、非允许域拒绝；
- 文本 MIME 正常读取；
- 二进制 read 拒绝并建议 export；
- Content-Length 超限；
- 流式实际字节超限；
- URL/header 不出现在异常；
- HTTP 错误安全摘要。

新增 `tests/test_media_service.py`：

- 笔记分支调用 Notes 一次；
- 笔记分支不调用 Source；
- URL 分支调用 Source，不调用 Notes；
- unavailable 分支不调用二级客户端；
- Knowledge 失败立即停止；
- note ID 缺失为协议错误；
- 文本导出 UTF-8 字节准确；
- 二进制导出保持字节不变；
- 目标存在默认拒绝；
- `force` 成功替换；
- 中途失败删除临时文件并保留原目标；
- SHA-256 和 byte count 正确。

### B2.5 增加 CLI 命令

修改 `knowledge_cli.py`，注册：

```text
ima kb media-info --media-id MEDIA_ID [--json]
ima kb read --media-id MEDIA_ID [--json]
ima kb export --media-id MEDIA_ID --output PATH [--force] [--json]
```

输出约定：

`media-info`：

- 人类模式显示 media_id、media_type、source kind、available；
- URL 分支最多显示安全 host 和 header 名列表；
- 不显示完整 URL/query/header values；
- Notes 分支显示 note_id。

`read`：

- 人类模式显示安全元数据和文本正文；
- JSON 包含 `content`、`content_type`、`source_kind`；
- 二进制返回 `media_binary_requires_export`；
- 不自动落盘。

`export`：

- 成功显示目标路径、字节数和 SHA-256；
- JSON 同时包含 media_id、media_type、source_kind、content_type；
- 默认不覆盖；
- `--force` 显式覆盖。

### B2.6 调整顶层 client 构造

修改 `cli.py`：

- 从同一 Credentials 快照构造 client；
- 普通 Knowledge 命令不构造 Notes/Source client；
- 媒体命令按需构造 `MediaContentService`；
- 将 command name 和 JSON mode 传给统一错误出口；
- `KeyboardInterrupt` 返回 130；
- 未预期异常返回通用 70；
- 不再把任意 `ValueError` 当作用户错误，所有已知输入点迁移为 `InputError`。

### B2.7 维护公共 Python API

修改 `api.py`：

- 导出 `ImaCliError` 和新 API 错误子类；
- 继续导出 `ApiError`；
- 导出 `MediaInfo`、`MediaAccessInfo`；
- 视公共用途导出 `MediaContentService` 的结果模型；
- 不导出包含临时 headers 的裸 dict；
- 不改变 `ImaNoteApiClient` 别名。

`__init__.__version__` 本批次继续作为 User-Agent 版本来源；版本单一来源重构留给批次 D。

### B2.8 更新 CLI 和输出测试

扩展 `tests/test_cli.py`：

- 所有现有 `--json` 成功结果增加公共字段；
- 现有命令专属字段仍位于顶层；
- JSON 输入、配置、网络、业务、协议、媒体错误；
- JSON 错误 stdout 是单个合法文档且 stderr 为空；
- 人类错误只在 stderr；
- exit code 分类；
- `auth` 三层来源；
- `media-info` 不泄露 URL/header；
- `read` Notes 跨模块；
- `read` URL 文本；
- `export` 参数和结果；
- parser error 在 `--json` 时结构化；
- `--help` 仍正常退出。

Fake clients 必须记录调用，避免测试只检查输出而遗漏路由。

### B2.9 更新活动文档

修改 `README.md`：

- 三层凭证优先级和用户配置示例；
- `ima auth` 来源说明；
- 公共 JSON envelope；
- 错误退出码表；
- `media-info`、`read`、`export` 用法；
- 原文安全与大小限制；
- URL 原文读取和批次 C 的用户 URL 探测边界；
- 更新项目结构。

修改 `skills/ima-note-cli/SKILL.md`：

- 用户配置目录；
- 新媒体命令；
- JSON 错误处理；
- 安全提示；
- 不要求输出凭证或签名 URL。

修改 `docs/API_CONTRACT_1_1_7.md`：

- 链接 Knowledge/Media 契约；
- 记录共享 HTTP envelope、错误和重试规则；
- 保持 Notes 批次 A 裁决不变。

不修改 `skills/ima-skills-1.1.2` 历史快照，也不直接编辑用户提供的 `ima-skills-1.1.7 (1)` 来源目录。

## 6. 涉及文件

### 6.1 新增文件

| 文件 | 作用 |
| --- | --- |
| `BATCH_B_IMPLEMENTATION_PLAN.md` | 本详细计划 |
| `docs/KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md` | Knowledge/Media 契约裁决 |
| `src/ima_note_cli/errors.py` | 错误层级、机器码和退出码 |
| `src/ima_note_cli/output.py` | 公共 JSON/human 输出 |
| `src/ima_note_cli/protocol.py` | 严格响应字段解析 |
| `src/ima_note_cli/security.py` | IMA/COS/媒体 URL 和敏感信息安全策略 |
| `src/ima_note_cli/source_http.py` | 不携带长期凭证的原文 GET/流式导出 |
| `src/ima_note_cli/media_service.py` | get_media_info、Notes、URL 的跨模块编排 |
| `tests/test_errors.py` | 错误层级和退出码测试 |
| `tests/test_output.py` | JSON envelope 和输出通道测试 |
| `tests/test_protocol.py` | 严格字段解析测试 |
| `tests/test_security.py` | URL/domain/header/redaction 测试 |
| `tests/test_source_http.py` | 原文 HTTP、重定向、大小和泄露测试 |
| `tests/test_media_service.py` | 跨模块读取和导出测试 |
| `tests/fixtures/knowledge/README.md` | Knowledge fixture 规则 |
| `tests/fixtures/knowledge/*.json` | 脱敏 Knowledge/Media wire fixtures |

### 6.2 修改文件

| 文件 | 改动 |
| --- | --- |
| `OPTIMIZATION_PLAN.md` | 链接本计划 |
| `README.md` | 配置、JSON、退出码和原文命令 |
| `src/ima_note_cli/http.py` | 官方域、大小限制、错误分类、重试、User-Agent |
| `src/ima_note_cli/config.py` | 三层来源和单次解析 |
| `src/ima_note_cli/cli.py` | 统一错误出口、JSON parser error、媒体服务注入 |
| `src/ima_note_cli/notes_api.py` | 共享严格解析和 read/write 分类 |
| `src/ima_note_cli/knowledge_api.py` | 严格解析、限制、get_media_info 模型/方法 |
| `src/ima_note_cli/notes_cli.py` | 公共 JSON emitter 和 InputError |
| `src/ima_note_cli/knowledge_cli.py` | 公共输出、限制和媒体命令 |
| `src/ima_note_cli/knowledge_upload.py` | 统一错误和 COS 域名保护 |
| `src/ima_note_cli/api.py` | 公共错误和媒体模型导出 |
| `tests/_fixtures.py` | Knowledge fixture 支持 |
| `tests/test_http.py` | HTTP 大小、重试、redaction 和域名 |
| `tests/test_config.py` | 三层优先级、单次读取和错误 |
| `tests/test_cli.py` | JSON envelope、退出码和媒体命令 |
| `tests/test_notes_api.py` | read/write 分类和严格解析回归 |
| `tests/test_knowledge_api.py` | Knowledge 全契约和 get_media_info |
| `tests/test_knowledge_upload.py` | COS 域名和安全错误 |
| `skills/ima-note-cli/SKILL.md` | CLI 配置和新命令 |
| `docs/API_CONTRACT_1_1_7.md` | 链接共享/Knowledge 契约 |

### 6.3 预计无需修改

- `pyproject.toml`；
- `uv.lock`；
- `src/ima_note_cli/notes_content.py`；
- `skills/ima-skills-1.1.2`；
- `ima-skills-1.1.7 (1)`；
- GitHub Actions；
- 发布元数据和 LICENSE；
- COS 流式上传主体；
- 用户输入 URL 的检测/下载流程。

若实施中需要新增生产依赖、开放其他域名、改变现有命令专属 JSON 字段路径，必须先重新确认，而不能作为“顺手优化”并入。

## 7. 验收矩阵

### 7.1 错误和退出码

- [x] 所有预期用户错误都继承 `ImaCliError`；
- [x] 输入错误返回 2；
- [x] 配置错误返回 3；
- [x] 网络/超时返回 4；
- [x] IMA 业务错误返回 5；
- [x] 协议错误返回 6；
- [x] 原文/本地 I/O 返回 7；
- [x] 上传错误返回 8；
- [x] 未预期错误返回无底层详情的 70；
- [x] `KeyboardInterrupt` 返回 130；
- [x] 不再以捕获所有 `ValueError` 的方式隐藏程序缺陷；
- [x] `ApiError`、`ConfigError` 和 `KnowledgeUploadError` 兼容导入仍可用。

### 7.2 JSON 和输出通道

- [x] 每个成功 JSON 有 `schema_version=1`、`ok=true`、`command`、`warnings`；
- [x] 现有命令专属字段仍位于原顶层路径；
- [x] 每个失败 JSON 有 `ok=false` 和稳定 `error` 对象；
- [x] JSON 成功和失败都只产生一个合法 JSON 文档；
- [x] JSON 失败时 stderr 为空；
- [x] 人类错误只写 stderr；
- [x] 参数解析失败在带 `--json` 时也是结构化错误；
- [x] `--help` 仍为正常人类帮助；
- [x] 输出不包含凭证、临时 headers、签名 URL 或原始错误正文。

### 7.3 配置

- [x] 环境变量覆盖 `.env` 和用户配置；
- [x] `.env` 覆盖用户配置；
- [x] `~/.config/ima/client_id` 和 `api_key` 可单独回退；
- [x] 混合来源按字段正确报告；
- [x] 同一命令每个配置文件最多读取一次；
- [x] 非法 UTF-8、无权限和目录冒充文件产生 ConfigError；
- [x] `ima auth` 只显示来源和 set/missing，不显示值；
- [x] 缺少凭证时 `auth` 返回 3；
- [x] 测试不读取真实 home 配置。

### 7.4 HTTP 与安全边界

- [x] IMA 长期凭证只发往 `https://ima.qq.com`；
- [x] 非官方 Base URL 在发请求前失败；
- [x] endpoint authority 注入被拒绝；
- [x] User-Agent 包含 CLI 版本；
- [x] 成功 JSON 正文超过 4 MiB 时失败；
- [x] HTTP error 正文最多读取 16 KiB；
- [x] 错误摘要最多 512 字符并经过清洗；
- [x] read endpoint 最多 3 次尝试；
- [x] write endpoint 永不自动重试；
- [x] 业务和协议错误不重试；
- [x] COS host 注入在签名前失败；
- [x] COS 临时凭证只发往合法 `*.myqcloud.com`；
- [x] 原文客户端从不携带 IMA Client ID/API Key。

### 7.5 严格协议

- [x] 必填集合缺失/null/错误类型不会变为空集合；
- [x] `str(None)` 不再出现在 API 模型；
- [x] `"false"`、`"0"` 不会被当作 true；
- [x] 关键 note/folder/kb/media ID 缺失时返回协议错误；
- [x] `create_media` 缺 media_id/cos_credential 时失败；
- [x] `add_knowledge` 缺 media_id 时失败；
- [x] `import_urls` 成功项缺 media_id 时失败；
- [x] 所有协议错误包含 endpoint 和字段路径；
- [x] 协议错误不回显字段值。

### 7.6 输入限制

- [x] KB 搜索 limit 只允许 1–20；
- [x] KB browse/addable limit 只允许 1–50；
- [x] get KB IDs 只允许 1–20 个且唯一；
- [x] import URLs 只允许 1–10；
- [x] repeated names 参数只允许 1–2000；
- [x] Python API 绕过 CLI 时仍执行同样校验；
- [x] 所有无效输入在网络调用前失败。

### 7.7 get_media_info

- [x] 请求 endpoint 为 `get_media_info`；
- [x] payload 只含非空 `media_id`；
- [x] URL 分支解析 media_type/url/headers；
- [x] Notes 分支映射 `notebook_id -> note_id`；
- [x] unavailable 分支是合法元数据；
- [x] 缺 media_type、note_id 或错误 headers 产生协议错误；
- [x] 冲突分支不被静默猜测；
- [x] 模型 repr 和安全 JSON 不包含 header values；
- [x] media-info 不显示完整签名 URL。

### 7.8 跨模块读取

- [x] media_type 11 只调用 Notes `get_doc_content`；
- [x] Notes 分支不调用 URL 客户端；
- [x] URL 分支不调用 Notes；
- [x] unavailable 分支不发第二个请求；
- [x] Knowledge 失败后停止；
- [x] `kb read` 能返回笔记正文；
- [x] URL 文本只在允许 MIME 和 4 MiB 内读取；
- [x] 二进制 read 明确提示使用 export；
- [x] 临时 Authorization 不会跨源重定向；
- [x] URL/query/header 不出现在错误或 JSON。

### 7.9 导出

- [x] 笔记导出为严格 UTF-8；
- [x] 二进制导出保持原始字节；
- [x] 以 64 KiB 块流式处理；
- [x] 最大 200 MiB；
- [x] 默认拒绝覆盖；
- [x] `--force` 也使用临时文件加原子替换；
- [x] 失败删除临时文件；
- [x] 失败不破坏原目标文件；
- [x] bytes 和 SHA-256 正确；
- [x] JSON 不包含临时路径和访问凭证。

### 7.10 回归、文档和工作区

- [x] 批次 A 的 66 个基线测试全部继续通过；
- [x] 新测试不访问真实网络；
- [x] 新测试不读取真实凭证目录；
- [x] 不新增生产依赖；
- [x] README 与 CLI help 一致；
- [x] 活动 CLI skill 与实现一致；
- [x] 1.1.7 来源目录保持未修改；
- [x] 批次 C/D 功能未提前混入；
- [x] 工作区不存在测试导出残留或临时文件。

## 8. 验证命令

实施过程中按聚焦顺序执行：

```bash
uv run python -m unittest tests.test_errors tests.test_output tests.test_protocol -v
uv run python -m unittest tests.test_security tests.test_http tests.test_config -v
uv run python -m unittest tests.test_knowledge_api tests.test_notes_api -v
uv run python -m unittest tests.test_source_http tests.test_media_service -v
uv run python -m unittest tests.test_cli tests.test_knowledge_upload -v
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
```

静态检查：

```bash
rtk rg -n "str\(.*get\(|bool\(.*get\(" src/ima_note_cli
rtk rg -n "IMA_OPENAPI_APIKEY|Authorization|secret_key|security-token" src tests
rtk rg -n "urlopen|build_opener|Request\(" src/ima_note_cli
rtk rg -n "get_media_info|media-info|kb read|kb export" src tests README.md skills/ima-note-cli
```

检查原则：

- 凭证词汇出现在 header 构造、redaction 规则和虚构测试中是允许的；
- 凭证值、真实签名 URL 和真实账户 ID 不允许出现；
- 所有网络调用点必须能对应到域名校验、大小上限和 retry 分类；
- `str(...)`/`bool(...)` 搜索允许出现在明确的展示转换中，不允许承担协议校验。

## 9. 可选的受保护只读 smoke

自动验收只依赖 mock/fixture。若有专用测试账户并经人工确认，可额外执行：

```text
ima auth --json
ima kb media-info --media-id "media_test_target" --json
ima kb read --media-id "note_media_test_target" --json
```

若验证 URL 原文，可导出到明确的临时路径：

```text
ima kb export --media-id "media_test_target" --output "./tmp-media-export.bin" --json
```

规则：

- 只使用专用测试账户；
- 不把真实 media_id、note_id、正文、host、headers 写入 fixture；
- 不打印或复制 `media-info` 内部原始模型；
- smoke 后删除临时导出；
- 不执行 create、append、import_urls、create_media、COS PUT 或 add_knowledge；
- 若 host 不在 allowlist，记录“域名类别”而不是完整签名 URL，再更新契约裁决；
- 任何新增允许域必须先确认是官方受控域。

## 10. 实施顺序与提交切片

### B-1：契约、错误和输出骨架

- Knowledge/Media 契约文档；
- Knowledge fixtures；
- `errors.py`；
- `output.py`；
- parser error 桥接；
- 错误/输出测试。

完成条件：现有命令仍可运行，所有 JSON 已有公共 envelope，错误分类测试通过。

### B-2：配置、域名和 HTTP

- 单次配置快照；
- 用户配置目录；
- `security.py`；
- HTTP 大小限制、安全摘要、User-Agent；
- read/write 分类和有限重试；
- COS 域名防护。

完成条件：长期凭证目标域和 retry 安全边界由测试锁定。

### B-3：严格协议和输入限制

- `protocol.py`；
- Notes 解析迁移；
- Knowledge 全接口解析迁移；
- 数量/分页限制；
- Knowledge fixtures 驱动测试。

完成条件：错误字段类型不再静默降级，全部既有功能回归通过。

### B-4：get_media_info 与原文服务

- Media 模型/API；
- `source_http.py`；
- `media_service.py`；
- Notes 跨模块路由；
- read/export 安全和清理测试。

完成条件：三种 media 分支、重定向、大小和临时文件不变量均通过。

### B-5：CLI、文档与总体验证

- 三个媒体命令；
- CLI Fake clients；
- README 和 CLI skill；
- 全量测试、compileall、静态搜索；
- 可选只读 smoke 记录。

每个切片都应保持测试绿色，不提交只含失败测试的中间状态。

## 11. 主要风险与应对

### 风险 1：公共 JSON 字段影响现有脚本

应对：

- 只增加公共字段，不移动现有命令字段；
- 保持 `note_id/doc_id` 兼容；
- Schema 固定为 1；
- 在 README 标明新增字段；
- 通过测试锁定旧字段路径。

### 风险 2：读取 POST 被误分类为写入或反之

应对：

- 不根据 HTTP method 自动判断；
- 使用命名明确的 `post_read_json`/`post_write_json`；
- 每个 endpoint 测试实际选择的调用；
- 新 endpoint 默认 write/no retry，必须显式声明 read。

### 风险 3：严格解析暴露真实 API 的历史不一致

应对：

- 以 1.1.7 reference 为主；
- 对已知 int64 字符串等兼容情况写入契约；
- 只读 smoke 只记录响应形状，不记录真实值；
- 不用 `str(None)` 或默认空集合掩盖问题。

### 风险 4：用户配置与项目 .env 混合成错误凭证对

应对：

- 保持当前字段级兼容行为；
- `ima auth` 明确显示两字段来源；
- 来源不同可给非阻断 warning；
- 不自动交换、猜测或尝试多组凭证。

### 风险 5：真实原文使用了 allowlist 外的官方 CDN

应对：

- 安全失败，不放开任意 HTTPS；
- 通过专用账户只读 smoke 确认；
- 只把明确官方域加入集中 allowlist；
- 新域必须有 fixture 和重定向测试。

### 风险 6：临时 headers 在重定向中泄露

应对：

- 使用自定义 RedirectHandler；
- 有临时 headers 时只允许同源；
- Request/错误/输出测试检查 header；
- Source client 永远不接收长期 Credentials。

### 风险 7：导出破坏现有文件

应对：

- 默认拒绝覆盖；
- 同目录临时文件；
- 完整写入、flush/close 后再原子替换；
- 失败保留旧目标并删除临时文件；
- 测试中注入中途失败。

### 风险 8：响应或原文过大

应对：

- Content-Length 前置检查；
- 实际读取字节二次限制；
- IMA JSON、read、export 使用不同上限；
- 超限错误只报告上限和已知类别，不报告 URL/正文。

### 风险 9：批次 B 扩张到批次 C

应对：

- 本批次只消费 `get_media_info` 返回的 URL；
- 不探测用户传入的 `add-url`；
- 不实现下载后上传；
- 不流式重构 COS PUT；
- 不实现冲突 rename 和批量上传。

### 风险 10：错误清洗降低诊断价值

应对：

- 保留 endpoint、HTTP status、attempts、字段路径；
- 业务错误保留清洗后的 `msg`；
- JSON 使用稳定 code；
- 不以回显原始正文换取诊断。

## 12. 完成定义

批次 B 只有在以下条件同时满足时才算完成：

1. 错误层级和退出码已实现并有测试。
2. 所有 `--json` 命令具有统一成功/失败公共字段。
3. JSON 错误不污染 stderr，人类错误不污染 stdout。
4. 配置支持环境变量、项目 `.env` 和用户配置，且每次只解析一次。
5. IMA 长期凭证不能被发送到非官方域名。
6. COS authority 注入在网络前被拒绝。
7. IMA 响应、错误摘要和原文均有明确大小上限。
8. 只有显式安全读取会有限重试，所有写操作不自动重试。
9. Notes 和 Knowledge 的关键字段使用严格协议解析。
10. `get_media_info` 三种响应分支都有 fixture 和测试。
11. 笔记型媒体可通过 Knowledge -> Notes 流程读取和导出。
12. URL 原文访问不携带长期凭证，临时 headers 不会跨源泄露。
13. 二进制原文可流式、安全、原子导出，失败无残留。
14. 现有 66 个批次 A 基线测试继续通过。
15. 新增测试全部离线、无真实凭证、无真实用户数据。
16. README、活动 CLI skill 和契约文档与实现一致。
17. 未新增生产依赖。
18. 未提前实施批次 C/D 的范围。

完成批次 B 后，再进入批次 C 的用户 URL 类型探测、下载再上传、COS 流式上传、冲突策略和 CLI 结构重构。
