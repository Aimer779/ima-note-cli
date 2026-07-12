# IMA OpenAPI 1.1.7 规范契约

本文件是仓库唯一规范 API 契约。代码、测试和脱敏 fixtures 是可执行证据；README 与 canonical skill 只描述用户工作流；[上游归档](../third_party/ima-skills/1.1.7/original)仅作来源证据，不是当前运行规范。

## 共享传输与 envelope

IMA 请求仅发送到官方 `https://ima.qq.com`。接口使用 POST JSON，响应必须是包含 `code`、`msg` 和对象型 `data` 的对象。成功 `code` 只接受整数 `0` 或字符串 `"0"`。读取请求在可重试网络/服务错误下最多两次重试，写入请求不重试；JSON 正文最大 4 MiB。非 JSON、缺字段、错误类型与非零业务码均明确失败。

## Notes 六个接口

所有 endpoint 相对于 `/openapi/note/v1`。

| 能力 | Endpoint | 请求要点 | 响应要点 |
| --- | --- | --- | --- |
| 搜索 | `search_note` | `search_type`、`sort_type`、`query_info`、`start`、`end` | `search_note_infos[]`、`is_end`、`total_hit_num` |
| 笔记本列表 | `list_notebook` | 首页 `cursor="0"`、`limit`、可选 `version` | `note_folder_infos[]`、`next_cursor`、`is_end` |
| 笔记列表 | `list_note` | `folder_id`、`sort_type`、首页空 cursor、`limit` | `note_book_list[]`、`is_end` |
| 读取正文 | `get_doc_content` | `note_id`、`target_content_format=0` | `content` |
| 创建 | `import_doc` | `content_format=1`、内容、可选 `folder_id` | `note_id` |
| 追加 | `append_doc` | `note_id`、`content_format=1`、内容 | `note_id` |

`note_id` 是模型、payload 和 CLI 的 canonical ID。兼容期内，`SearchResult.doc_id` 是只读别名，成功 JSON 可包含相等的 `note_id`/`doc_id`，`ima kb add-note --doc-id` 是 `--note-id` 的弃用别名。两者冲突时失败，不猜测旧响应树。

写入前严格验证 UTF-8。Markdown/HTML 图片只保留 HTTP(S) 引用；本地路径、data URI 与其他 scheme 被移除并报告，过滤后空内容失败。

## Knowledge 十一个工作流与核心接口

Knowledge API 覆盖知识库搜索/详情、内容浏览/搜索、可添加知识库、添加笔记、URL 导入、文件创建与重名检查、媒体信息和知识条目添加。集合字段必须保持数组/对象类型且关键 ID 非空；布尔不接受整数替代。限制为：知识库搜索 1–20，browse/addable 1–50，批量 IDs 1–20 且唯一，URL 1–10，重名检查 1–2000。

`create_media` 必须返回 media ID 与完整、限时 COS credential；`add_knowledge` 必须返回 media ID。`import_urls` 按请求顺序关联结果，非零 `ret_code` 是单项失败。命令处理器返回结构化结果，JSON schema 1 使用 `status`、`summary`、`pagination` 与单项 `stage`；partial 和逐项 batch failure 使用退出码 9 并保留可用结果。

## Media 原文

`POST /openapi/wiki/v1/get_media_info` 的 body 仅含 `media_id`。合法分支互斥：

- `media_type == 11` 必须包含 `notebook_ext_info.notebook_id`，内部映射为 `note_id`，且不得含 `url_info`；
- 非 11 且含 `url_info` 时，必须有非空 HTTPS URL，headers 必须是安全字符串映射；
- 非 11 且无 `url_info` 时，返回合法的 unavailable 元数据且不发第二个请求。

初始原文 URL 只允许 `ima.qq.com` 或标签边界正确的 `*.myqcloud.com` HTTPS host，并拒绝 userinfo、IP、localhost、非默认端口和控制字符。独立客户端不携带 IMA 长期凭证且拒绝跨源重定向。`read` 要求明确文本 MIME、最多 4 MiB 并按声明 charset 解码；`export` 以 64 KiB 流式处理、最多 200 MiB、默认不覆盖并原子替换。安全输出不包含完整签名 URL、query 或临时 header 值。

## 用户 URL 与 SSRF 边界

用户 URL 使用无凭证 `RemoteHttpClient`，不复用信任媒体客户端。只允许无 userinfo 的 HTTP(S) 默认端口；拒绝 IP literal、localhost、非公网 DNS 结果和 DNS rebinding。每次重定向都重新验证，最多五次；直连已解析公网 IP，同时保留正确 Host/SNI，不读取环境代理、cookie 或凭证。

探测优先 HEAD，只有可达的 405/501 才回退到有界 GET，不通过正文嗅探分类。Bilibili/YouTube 在联网前拒绝；HTML/微信走 `import_urls`，支持的文件 MIME/扩展名走有界下载上传。下载以 64 KiB 流式读取，验证 Content-Length/实际长度/SHA-256，使用自动清理的 `.part` 临时文件，最大值由文件预检规则决定。

## 文件与 COS 上传

上传 gate 顺序为：本地/远程文件预检、整批初始重名检查、冲突决策、`create_media`、COS PUT、文件身份复检、`add_knowledge`。文件名拒绝路径穿越、空名、Windows 保留名和不安全字符；支持类型、大小与 WAV 两小时边界在网络请求前验证。

默认 `--on-conflict error`；显式 rename 使用稳定时间后缀并至多尝试 100 个候选。最终名称必须一致用于 `create_media.file_name`、`file_info.file_name` 和 `add_knowledge.title`。COS PUT 固定 Content-Length、64 KiB 读取、不重定向、不重试，只连接 API 返回且校验为官方 myqcloud host 的目标；临时凭证时间和对象 key 均严格验证。创建 media 后的失败以 stage 标记并报告可能的 orphaned media。

## 分页、JSON 与退出语义

单页是默认行为。支持的 list/search 命令用 `--all --max-pages N` 做有界 cursor/offset 分页；重复 cursor 或页数上限产生 partial，而不是无限循环。JSON 成功和失败均为单个 stdout 文档，失败时 stderr 为空。退出码为：0 成功，2 输入，3 配置，4 网络，5 业务，6 协议，7 原文/本地 I/O，8 上传，9 partial/itemized failure，70 内部错误，130 中断。

## Fixtures 与来源

- [Notes fixtures](../tests/fixtures/notes/README.md)
- [Knowledge fixtures](../tests/fixtures/knowledge/README.md)
- [URL ingest fixtures](../tests/fixtures/url_ingest/README.md)
- [上游结构化来源](../third_party/ima-skills/1.1.7/UPSTREAM.json)
- [Third-party notices](../THIRD_PARTY_NOTICES.md)

Fixtures 均为离线、脱敏、合成数据，不得替换为真实账户响应、ID、签名、正文或凭证。

## 待受保护只读 smoke 验证

- `list_note` 是否始终返回 `next_cursor`，以及 `list_notebook` 增量版本语义；
- 实际媒体 URL host、Content-Type/Length、临时 headers 与重定向行为；
- 笔记媒体分支是否可能同时返回 `url_info`；
- URL 根目录 `folder_id` 和服务端错误码文档歧义。

不得用写入 smoke 验证这些项目。任何真实只读 smoke 都需人工确认，且不得把真实数据写入仓库。
