# ima-note-cli 仓库发现与优化实施计划

> 整理日期：2026-07-11  
> 参考来源：[`third_party/ima-skills/1.1.7/original`](third_party/ima-skills/1.1.7/original)  
> 当前阶段：阶段 6 已完成；阶段 7 尚未实施

## 1. 执行摘要

本次优化首先是一次 **IMA Notes API 从 1.1.2 契约迁移到 1.1.7 契约**，其次才是常规代码重构。

当前项目结构清晰、仅依赖 Python 标准库，并且已有笔记、知识库、COS 上传和 CLI 测试基础。这些优点应当保留。但现有笔记客户端仍使用 1.1.2 的端点、字段和响应层级；现有测试主要使用 Fake Client 验证 CLI 表层，因此即使 26 个测试全部通过，也无法证明真实 API 与 1.1.7 兼容。

推荐实施顺序：

1. 先建立 1.1.7 契约 fixtures 和测试安全网。
2. 迁移 Notes API 与 `note_id`。
3. 加固 HTTP、配置、错误和输入校验。
4. 补齐知识库原文、文件型 URL 和上传能力。
5. 重构 CLI 与输出层。
6. 最后统一 skills、文档、CI 和发布工程。

## 2. 仓库基线

### 2.1 当前状态

- 主分支：`main`，与 `origin/main` 对齐。
- 用户提供的 1.1.7 目录已按原始 bytes、SHA-256 和 MIT-0 来源证据归档。
- `skills/ima-note-cli` 是唯一 active skill；旧版 `ima-note` 与 1.1.2 skill 已迁移并删除。
- [`docs/IMA_OPENAPI_CONTRACT_1_1_7.md`](docs/IMA_OPENAPI_CONTRACT_1_1_7.md) 是唯一规范 API 契约。
- Python 运行时没有第三方生产依赖，`uv.lock` 仅包含本项目。

### 2.2 测试基线

执行：

```bash
uv run python -m unittest discover -s tests -v
```

结果：**26/26 测试通过**。

不过，测试覆盖集中在：

- CLI 参数和人类可读/JSON 输出；
- 凭证加载；
- Markdown 文件识别、视频拒绝；
- COS 签名的少量字段。

目前缺少：

- `http.py` 的请求、解包和异常测试；
- `notes_api.py` 的 1.1.7 请求/响应契约测试；
- `knowledge_api.py` 的接口契约测试；
- `add-file` 完整 Gate 顺序测试；
- COS 失败、超时、非法凭证测试；
- URL 类型探测和部分导入失败测试；
- `get_media_info` 和跨模块读取测试；
- 构建 wheel 后的 CLI 入口测试。

## 3. 当前架构

主要调用链：

```text
argparse CLI
  → 凭证检查/加载
  → NotesApiClient 或 KnowledgeBaseApiClient
  → 共享 HTTP 层
  → IMA OpenAPI
```

模块分工：

- `src/ima_note_cli/cli.py`：顶层命令、凭证加载和异常出口；
- `src/ima_note_cli/config.py`：环境变量与 `.env`；
- `src/ima_note_cli/http.py`：POST JSON 和响应解包；
- `src/ima_note_cli/notes_api.py`：笔记客户端及模型；
- `src/ima_note_cli/notes_cli.py`：笔记命令、编排和输出；
- `src/ima_note_cli/knowledge_api.py`：知识库客户端及模型；
- `src/ima_note_cli/knowledge_cli.py`：知识库命令、上传编排和输出；
- `src/ima_note_cli/knowledge_upload.py`：文件预检、COS 签名和上传。

值得保留的设计：

- API 客户端可注入，方便 CLI 测试；
- 多数实体使用冻结 dataclass；
- 笔记和知识库模块已经分离；
- 文件上传已经遵守“COS 成功后才调用 `add_knowledge`”；
- 文件标题已经使用原始文件名；
- Python HTTP 请求体已经显式编码为 UTF-8 字节，不受 PowerShell 5.1 字符串 Body 转码问题影响。

## 4. 关键发现

### 4.1 P0：Notes API 使用旧契约

当前 `src/ima_note_cli/notes_api.py` 仍基于 1.1.2：

| 当前实现 | 1.1.7 契约 |
| --- | --- |
| `search_note_book` | `search_note` |
| `list_note_folder_by_cursor` | `list_notebook` |
| `list_note_by_folder_id` | `list_note` |
| `doc_id` / `docid` | `note_id` |
| `docs[].doc.basic_info` | `search_note_infos[].note_book_info` |
| `note_book_folders[].folder.basic_info` | `note_folder_infos[]` |
| 多层 `basic_info` | 扁平 `NoteBookInfo` / `NoteFolderInfo` |
| `highlight_info` | `highlightInfo` |

受影响范围：

- Notes API 请求路径与 payload；
- 搜索、列表、笔记本响应解析；
- 创建、追加、读取参数和返回字段；
- CLI 参数、JSON 输出和帮助文本；
- `kb add-note` 的笔记 ID；
- README 和项目 skills；
- 所有 Fake Client 与测试 fixtures。

建议内部统一为 `note_id`。为避免突然破坏现有脚本，可让 `--doc-id` 作为一个版本周期的兼容别名，并输出弃用提示。

### 4.2 P0：测试通过但无法发现 API 漂移

`tests/test_cli.py` 主要替换整个 API Client，因此不会验证：

- 实际调用了哪个 endpoint；
- payload 字段是 `doc_id` 还是 `note_id`；
- 返回值来自 `docs` 还是 `search_note_infos`；
- 必填字段缺失时是否应该失败；
- HTTP 业务错误是否被正确解析。

因此，实施任何迁移前必须先添加 API 契约测试，而不是直接修改 CLI 测试使其继续通过。

### 4.3 P1：HTTP 与响应模型过于宽松

当前风险包括：

- `SUCCESS_CODE_VALUES` 包含 `None`，没有 `code` 的响应也会被当作成功；
- 大量方法返回异构 `dict[str, Any]`；
- `str(None)` 可能产生字符串 `"None"`；
- `bool("0")`、`bool("false")` 都会被解析为 `True`；
- 嵌套字段为 `null` 或错误类型时可能抛出未包装异常；
- 创建笔记、创建 media、添加知识缺少关键 ID 时仍可能显示成功；
- HTTP 错误和响应正文没有大小上限；
- `--json` 模式下错误仍是普通文本，缺少稳定机器契约。

建议建立：

- `ImaCliError` 基类；
- 配置、输入、协议、网络、业务、上传等子类；
- 带 endpoint 和可重试信息的 `ApiProtocolError`；
- 严格的字符串、布尔值、整数、对象和数组解析器；
- 明确的分页与写入结果 dataclass；
- 稳定 JSON 错误结构和退出码。

### 4.4 P1：凭证来源和安全边界需要统一

当前 CLI 只读取：

1. 环境变量；
2. 当前工作目录 `.env`。

1.1.7 同时支持 `~/.config/ima/client_id` 和 `~/.config/ima/api_key`。建议：

- 保持环境变量最高优先级；
- 增加用户配置目录回退；
- 保留 `.env` 作为本地开发兼容来源；
- 明确并测试三者的完整优先级；
- `ima auth` 显示来源路径，但绝不显示凭证值；
- IMA Base URL 保持固定为官方域名，或执行严格白名单；
- COS 仅允许 `*.myqcloud.com` 且必须使用 `create_media` 返回的短期凭证。

不建议照搬 `ima_api.cjs` 的以下行为：

- 将凭证放入命令行 options JSON；
- 接受任意 `IMA_BASE_URL`；
- 把 Node.js 变成 Python CLI 的生产运行时依赖；
- 在每次 CLI 请求前执行 skill 自更新检查。

### 4.5 P1：笔记写入规则未完全落实

1.1.7 要求：

- `import_doc` 与 `append_doc` 必须明确区分；
- 追加是不可撤销操作，目标必须明确；
- 所有写入字符串必须是合法 UTF-8；
- Markdown 中的本地图片引用必须过滤并告知用户；
- HTTP/HTTPS 网络图片可以保留。

当前 Python 字符串通常已经是 Unicode，文件也用 UTF-8 读取，但仍需处理：

- 非 UTF-8 文件的清晰错误；
- 孤立代理字符等无法合法编码的字符串；
- 本地图片 Markdown；
- `--json` 输出中报告被过滤的图片；
- 写入前的空内容与大小检查。

### 4.6 P1：知识库缺少 1.1.7 增量能力

已有能力：

- 搜索和查看知识库；
- 浏览与搜索知识库内容；
- 获取可添加知识库；
- 添加笔记、URL、本地文件；
- 文件重名检查；
- `create_media`、COS 上传和 `add_knowledge`。

主要缺口：

- `get_media_info`；
- 原文查看、分析和导出；
- `media_type=11` 时调用 Notes `get_doc_content`；
- 文件型 URL 的 HEAD/重定向/MIME/Content-Disposition 探测；
- 下载临时文件后走完整文件上传流程；
- 视频、Bilibili、YouTube、`file://` 的明确拒绝；
- URL 导入部分失败的非零退出语义；
- 各接口的最大数量和分页限制。

主要限制应覆盖：

- Notes 分页最多 20；
- 知识库搜索最多 20；
- 浏览和可添加列表最多 50；
- URL 导入每次 1–10 个；
- 知识库详情 ID 每次 1–20 个且不能重复；
- 重名检查每次最多 2000 个。

### 4.7 P1：上传链路是高风险区域

当前正确的 Gate 顺序是：

```text
文件预检
  → check_repeated_names
  → create_media
  → COS PUT
  → add_knowledge
```

已有的不变量：

- 上传失败后不会继续 `add_knowledge`；
- `title == file_name`；
- 二进制文件不会转码；
- 已拒绝常见视频文件；
- 已实现类型和大小限制。

待解决问题：

- 使用 `read_bytes()` 一次将最高 200 MB 文件载入内存；
- 预检和读取之间文件可能变化；
- `--content-type` 可能与扩展名冲突；
- COS 凭证字段缺失时错误出现得过晚；
- COS key/path 未充分规范化；
- 默认超时只有 120 秒且 CLI 不可配置；
- 同名文件目前直接失败；
- COS 成功但 `add_knowledge` 失败时可能产生孤立 media；
- HTML/MHTML 应提示改走 URL 导入；
- 空文件、文件名长度、凭证有效期、音频时长尚未验证。

重名策略建议：

- 默认 `--on-conflict error`，安全停止；
- 可选 `--on-conflict rename`，在扩展名前增加 `_YYYYMMDDHHmmss`；
- 不支持静默替换已有内容；
- 批量上传先一次性检查重名，再逐项处理。

### 4.8 P1：CLI 文件职责过重

当前热点文件：

- `knowledge_cli.py`：约 437 行；
- `knowledge_api.py`：约 374 行；
- `notes_cli.py`：约 374 行；
- `tests/test_cli.py`：约 532 行。

CLI 文件同时承担：

- 参数定义；
- 输入校验；
- API 编排；
- 上传工作流；
- 人类输出；
- JSON 序列化。

建议拆分为：

- `commands/`：命令注册和薄分发；
- `services/`：笔记、知识库、上传和媒体读取工作流；
- `models/`：请求结果和分页模型；
- `validation.py`：ID、limit、URL、文件和 UTF-8；
- `output.py`：人类输出和 JSON Schema；
- `errors.py`：错误层级和退出码。

是否实际采用目录拆分，应以降低复杂度为标准，不为拆分而拆分。

### 4.9 P2：skills、文档和发布元数据漂移

当前问题：

- README 说自带两个 skill，但 `skills/` 实际有三个目录；
- 旧版 1.1.2、新版 1.1.7、`ima-note` 和 `ima-note-cli` 同时存在；
- README 与 skills 仍使用 `doc_id`；
- README 和 `skills/ima-note-cli` 对凭证优先级的描述不完全一致；
- `pyproject.toml` 描述仍只强调搜索和读取笔记；
- 版本 `0.1.0` 同时写在 `pyproject.toml` 和 `__init__.py`；
- 没有 `ima --version`；
- 声明 MIT，但缺少 LICENSE 文件；
- 没有固定 tag、CHANGELOG 或发布流程；
- 当前 wheel 只打包 `src`，不会包含根目录 `skills/`。

需要先决定 skills 是：

1. 仅仓库资产；或
2. 随 Python 包分发的资源；或
3. 独立发布的技能包。

之后再配置 package data 和安装命令，避免 README 与实际分发行为继续不一致。

### 4.10 P2：缺少工程化门禁

当前没有：

- CI workflow；
- 正式 coverage 配置；
- formatter/linter；
- 类型检查；
- pre-commit；
- wheel/sdist 构建检查；
- 干净环境安装测试；
- 跨平台测试；
- `.gitattributes` 或 `.editorconfig`。

Windows 是一级平台，应至少与 Linux 一起进入 CI 矩阵。

## 5. 1.1.7 资料中的歧义

1.1.7 不能机械覆盖旧实现，实施前需要建立契约裁决表：

1. `import_urls.folder_id`：一处要求根目录时省略，API reference 又规定必填且根目录传 `knowledge_base_id`。
2. `list_note`：请求包含 cursor，但响应结构没有清晰列出 `next_cursor`。
3. Notes 错误码：SKILL 与 reference 使用不同错误码段。
4. `create_media.file_ext`：reference 规定必填，前置脚本却允许无扩展名并输出空值。
5. 音频 `media_type=15` 是否必须参与重名检查，文档描述不一致。
6. 上传 Gate 和步骤编号在不同章节中不一致。
7. 安全声明只允许官方域名，但 `ima_api.cjs` 接受任意 `IMA_BASE_URL`。
8. `application/zip` 被直接视为 Xmind，可能误判普通 ZIP。
9. 人类输出指南希望隐藏内部 ID，但当前 CLI 的后续命令依赖这些 ID。
10. 更新检查只比较版本是否不同，本地版本更高也可能被错误判定为需要更新。

裁决原则：

- 以明确的 API 请求/响应结构为主；
- 以实际脱敏响应 fixture 或受保护的只读 smoke 结果验证；
- 后端业务错误优先展示 `msg`，不把错误码文案硬编码为唯一事实；
- 安全默认值优先；
- CLI 兼容性通过显式别名和弃用周期处理。

## 6. 分阶段实施计划

### 阶段 0：建立契约与测试安全网（P0）

目标：在修改实现前，让测试能够准确识别 1.1.2/1.1.7 差异。

任务：

- [ ] 新建 1.1.7 契约裁决文档；
- [ ] 为 Notes 六个接口建立脱敏成功/错误 fixtures；
- [ ] 为 Knowledge Base 十个接口建立核心 fixtures；
- [ ] 增加 HTTP 成功、业务错误、HTTP 错误、网络错误、超时、非法 JSON 和错误响应形状测试；
- [ ] 增加每个 endpoint 的请求路径和 payload 测试；
- [ ] 增加必填字段缺失、错误类型和 `null` 测试；
- [ ] 固化上传 Gate 顺序及“失败后停止”不变量；
- [ ] 记录所有尚待真实 API 验证的歧义。

验收标准：

- 旧 Notes 实现会被新版契约测试准确判定失败；
- fixtures 不包含真实凭证、私有笔记内容或敏感 URL；
- 测试不访问真实网络。

### 阶段 1：迁移 Notes API（P0）

目标：使笔记查询、读取、创建和追加完全兼容 1.1.7。

任务：

- [ ] 切换 `search_note`、`list_notebook`、`list_note`；
- [ ] 请求和返回字段统一为 `note_id`；
- [ ] 重写搜索、列表、笔记本解析器；
- [ ] 为 `NoteBookInfo`、`NoteFolderInfo` 和分页结果建立明确模型；
- [ ] 增加 `sort_type`、limit、cursor 和空输入校验；
- [ ] 过滤 Markdown 本地图片并报告结果；
- [ ] 显式校验写入字符串可编码为 UTF-8；
- [ ] 保留 `doc_id`/`--doc-id` 短期兼容层；
- [ ] 更新 Fake Client、CLI 输出和 JSON 字段。

验收标准：

- Notes API 契约测试全部通过；
- 现有 CLI 用法除弃用提示外保持可用；
- 写入前可检测非法 Unicode 与本地图片；
- 所有关键 ID 缺失均返回协议错误，而不是空成功结果。

### 阶段 2：加固 HTTP、配置和错误模型（P1）

目标：让 API 漂移、配置问题和网络故障可诊断且适合自动化。

任务：

- [ ] 建立统一错误层级和退出码；
- [ ] 严格校验 `code`、`data` 和关键字段；
- [ ] 增加响应正文大小限制和安全错误摘要；
- [ ] `--json` 输出稳定的成功/失败 Schema；
- [ ] 只对安全的读取操作执行有限退避重试；
- [ ] 增加 `~/.config/ima` 凭证来源；
- [ ] 统一并记录环境变量、`.env`、用户配置的优先级；
- [ ] 避免重复解析 `.env`；
- [ ] 校验官方 IMA 和 COS 域名；
- [ ] 增加 CLI 版本/User-Agent 上下文，但不照搬不安全的任意 Base URL。

验收标准：

- 所有异常转换为稳定、无敏感信息的 CLI 错误；
- JSON 模式不混入人类文本；
- `ima auth` 能说明来源且不打印值；
- 不会将 IMA 长期凭证发送到非官方域名。

### 阶段 3：补齐知识库原文与 URL 流程（P1）

目标：覆盖 1.1.7 的知识库查询、原文和导入能力。

任务：

- [ ] 实现 `get_media_info` 模型与客户端；
- [ ] 增加媒体信息、查看原文和导出命令；
- [ ] `media_type=11` 时转调 Notes `get_doc_content`；
- [ ] URL 类型探测支持重定向、MIME 和 Content-Disposition；
- [ ] 文件型 URL 下载到安全临时目录后走完整上传流程；
- [ ] 限制下载大小并确保临时文件清理；
- [ ] 明确拒绝 `file://`、视频、Bilibili 和 YouTube；
- [ ] 对 URL 批量导入部分失败返回明确状态和非零退出码；
- [ ] 落实所有数量和分页上限。

验收标准：

- URL 页面与文件型 URL 会进入正确工作流；
- 下载和导出不会泄露 Authorization 等临时头；
- 笔记媒体可以通过跨模块流程读取；
- 每种失败分支均有测试。

### 阶段 4：强化上传服务（P1）

目标：在大文件、重名和阶段性失败场景下保持安全、可恢复和低内存。

任务：

- [ ] 抽取独立 Upload Service；
- [ ] 改为流式 COS 上传；
- [ ] 上传前后复核文件大小和修改状态；
- [ ] 校验 COS 凭证完整性、域名和有效期；
- [ ] 正确规范化 COS key/path；
- [ ] 默认超时调整为可配置的 300 秒；
- [ ] 实现 `--on-conflict error|rename`；
- [ ] 支持批量文件预检和一次性重名检查；
- [ ] 拒绝空文件、超长文件名和 MIME/扩展名冲突；
- [ ] 为孤立 media 提供明确提示或可行的补偿策略；
- [ ] 评估音频时长检查是否能用标准库实现。

验收标准：

- 上传 200 MB 文件时不会一次性载入全部内容；
- COS 失败后绝不调用 `add_knowledge`；
- `add_knowledge.title` 始终等于最终文件名；
- 默认不覆盖或静默替换同名文件；
- 每个 Gate 的失败路径均有测试。

若音频时长检查需要新增生产依赖，实施前必须先确认。

### 阶段 5：重构 CLI、模型和输出（P1）

目标：降低大型 CLI 文件复杂度，同时保持命令兼容。

任务：

- [ ] 分离命令注册、工作流、校验和输出；
- [ ] 用明确类型替换已知模型上的 `object/getattr`；
- [ ] 抽取共享 limit、cursor、ID、URL 校验；
- [ ] 增加统一 `--all`/分页策略及最大页数保护；
- [ ] 定义稳定 JSON Schema；
- [ ] 统一成功、空结果、部分成功和失败退出码；
- [ ] 为人类输出优先展示名称，JSON 保留完整 ID；
- [ ] 评估按名称解析知识库、文件夹和笔记，减少手工复制 ID。

验收标准：

- CLI 行为由回归测试覆盖；
- JSON 字段在同类命令中保持一致；
- 业务编排可以脱离 stdout 独立测试；
- 不使用 `argparse` 私有类型作为核心公共接口。

### 阶段 6：统一 skills 与文档（P2）

详细文件级计划见 [STAGE_6_IMPLEMENTATION_PLAN.md](STAGE_6_IMPLEMENTATION_PLAN.md)。

目标：消除多版本漂移并让文档与实际分发一致。

任务：

- [x] 将下载目录规范化，不保留 `(1)` 后缀作为正式路径；
- [x] 记录上游版本、来源、许可证和校验信息；
- [x] 确定唯一 canonical skill；
- [x] 迁移验证完成后淘汰或归档 1.1.2；
- [x] 统一 active skill 的 endpoint、`note_id` 和命令；
- [x] 更新 README 功能、配置、上传、原文和错误说明；
- [x] 决定 skills 为 repository-only，不随 wheel 分发；
- [x] 增加技能元数据、版本和 Markdown 链接一致性检查；
- [x] 保留 MIT-0 上游归属说明。

验收标准：

- 仓库只有一个活动 API 契约来源；
- README、CLI help、skills 和代码字段一致；
- 安装说明与实际包内容一致；
- 不丢失上游许可证和来源信息。

### 阶段 7：工程化、打包与发布（P2）

目标：建立可重复、跨平台、可发布的质量门禁。

任务：

- [ ] 增加 Windows + Linux CI；
- [ ] 测试最低支持 Python 和最新稳定 Python；
- [ ] 增加正式 branch coverage，初始整体门槛建议 80%；
- [ ] 协议、错误和上传关键路径设置更高要求；
- [ ] 配置 formatter、linter 和类型检查；
- [ ] 提供统一本地 `check` 命令；
- [ ] 增加 `uv lock --check`、单测、构建和 wheel 安装 smoke；
- [ ] wheel 安装后验证 `ima --help`、`ima-note --help`；
- [ ] 统一版本来源并增加 `ima --version`；
- [ ] 补充 LICENSE、项目 URL、维护者和问题链接；
- [ ] 增加 `.gitattributes`、`.editorconfig` 和行尾检查；
- [ ] 使用语义化 tag、CHANGELOG 和固定版本安装示例。

如果最终保留并分发 CJS 文件，CI 还应在 Node.js 18 下执行语法和行为测试；否则 Node 不应成为 CLI 的运行时要求。

验收标准：

- 所有 PR 自动通过跨平台测试和质量门禁；
- 构建出的 wheel 能在干净环境运行两个入口；
- 版本、许可证和安装文档完整；
- 发布流程不依赖开发机的隐式状态。

## 7. 推荐实施批次

为降低审查和回滚风险，建议拆为四个可独立验证的批次：

### 批次 A：契约安全网与 Notes 迁移

详细文件级计划见 [BATCH_A_IMPLEMENTATION_PLAN.md](BATCH_A_IMPLEMENTATION_PLAN.md)。

- 阶段 0；
- 阶段 1；
- Notes 文档的最小同步。

### 批次 B：公共基础与原文能力

详细文件级计划见 [BATCH_B_IMPLEMENTATION_PLAN.md](BATCH_B_IMPLEMENTATION_PLAN.md)。

- 阶段 2；
- 阶段 3 中的 `get_media_info` 和跨模块读取。

### 批次 C：URL、上传和 CLI 重构

详细文件级计划见 [BATCH_C_IMPLEMENTATION_PLAN.md](BATCH_C_IMPLEMENTATION_PLAN.md)。

- 阶段 3 的 URL 检测；
- 阶段 4；
- 阶段 5。

### 批次 D：skills、CI 与发布

- 阶段 6；
- 阶段 7。

每个批次都应保持测试通过，不把 API 迁移、上传重构和发布工程混在一个不可回滚的大改动中。

## 8. 总体验收标准

项目优化完成时应满足：

- [ ] Notes 请求和响应完全符合已裁决的 1.1.7 契约；
- [ ] Knowledge Base 覆盖 1.1.7 的十个核心接口；
- [ ] 所有写操作具备明确目标和安全默认值；
- [ ] 本地图片、非法 UTF-8、非法 URL、超限参数在请求前被处理；
- [ ] 上传严格遵守 Gate 顺序并使用低内存流式传输；
- [ ] 长期凭证只发送到官方 IMA 域名；
- [ ] JSON 输出和退出码可供脚本稳定使用；
- [ ] 旧 CLI 用法具有清晰的兼容和弃用周期；
- [ ] API、HTTP、上传和错误关键路径均有契约测试；
- [ ] Windows/Linux CI、覆盖率、格式、类型、构建和安装测试全部启用；
- [ ] skills、README、代码和发布包只有一个一致的事实来源。

## 9. 下一步

优先开始“阶段 0：建立契约与测试安全网”，随后立即执行 Notes 迁移。当前最大的风险不是代码结构，而是测试无法识别旧版 API 契约；先解决这一点，后续优化才有可靠基础。
