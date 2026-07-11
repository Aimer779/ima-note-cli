# Notes API 1.1.7 契约裁决

Knowledge 与媒体原文契约见 [KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md](KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md)。共享 HTTP 层要求对象型 `code/msg/data` envelope；成功 code 只接受整数 `0` 或字符串 `"0"`，读取接口最多尝试三次，写入接口不重试，成功 JSON 正文最大 4 MiB。

状态：批次 A 已实施  
依据：`ima-skills-1.1.7 (1)/notes/references/api.md` 与同版本 `notes/SKILL.md`  
适用范围：`src/ima_note_cli/notes_api.py`、wire fixtures 与 Notes CLI

## 已确认的接口

| 能力 | Endpoint | 请求要点 | 响应 `data` 要点 |
| --- | --- | --- | --- |
| 搜索 | `search_note` | `search_type`、`sort_type`、`query_info`、`start`、`end`；`end-start <= 20` | `search_note_infos[].note_book_info`、`highlightInfo`、`is_end`、`total_hit_num` |
| 笔记本列表 | `list_notebook` | 首页 `cursor="0"`、`limit`，可选 `version` | `note_folder_infos[]`、`next_cursor`、`is_end`、`next_version`、`need_update` |
| 笔记列表 | `list_note` | `folder_id`、`sort_type`、首页 `cursor=""`、`limit` | 扁平 `note_book_list[]`、`is_end` |
| 读取正文 | `get_doc_content` | `note_id`、固定 `target_content_format=0` | `content` |
| 创建 | `import_doc` | 固定 `content_format=1`、非空 `content`、可选 `folder_id` | 必填 `note_id` |
| 追加 | `append_doc` | `note_id`、固定 `content_format=1`、非空 `content` | 必填 `note_id` |

所有 endpoint 相对于 `https://ima.qq.com/openapi/note/v1`，均使用 POST JSON。标准 wire envelope 必须是含 `code`、`msg`、对象型 `data` 的 JSON 对象。`code` 为数值 `0` 或兼容字符串 `"0"` 时成功；缺少 `code`、缺少/非对象 `data`、非 JSON、非对象顶层响应均失败。非零 `code` 的错误包含后端 `msg`。

## 模型映射

- `NoteBookInfo.note_id` 是唯一正式 ID。
- `note_ext_info.folder_id` 与 `note_ext_info.folder_name` 映射笔记本信息。
- `cover_image` 原样保留，空值映射为空字符串。
- 搜索高亮只读取大小写敏感的 `highlightInfo.doc_title`。
- `NoteFolderInfo` 是扁平对象；1.1.7 未定义旧版 `status`。
- 关键笔记条目缺少 `note_id`、关键笔记本条目缺少 `folder_id` 时明确失败，不兼容猜测旧响应树。

## `note_id` 与兼容层

内部方法、payload、模型和 CLI Namespace 只使用 `note_id`。兼容期内：

- `SearchResult.doc_id` 是只读别名；兼容构造可传 `doc_id`，若与 `note_id` 同时提供且不同则失败。
- Notes 成功 JSON 以及 KB add-note 成功 JSON 同时输出相等的 `note_id`/`doc_id`。
- `ima kb add-note --doc-id` 保留为弃用别名；人类模式写 stderr 警告，JSON 模式写 `warnings`，不污染 JSON stdout。
- 位置参数语法不变：`ima note get NOTE_ID`、`ima note append NOTE_ID`。

## 写入安全裁决

写请求前对最终字符串执行严格 UTF-8 编码检查，孤立代理字符失败且不得发送。Markdown/HTML 图片仅保留 `http://` 与 `https://`；`file://`、盘符、UNC、绝对/相对/用户目录路径、data URI 及其他非网络图片引用被删除并报告。普通路径文本和普通链接不处理。过滤后只剩空白时失败。

## 待只读 smoke 验证

| 问题 | 当前裁决 | 状态 |
| --- | --- | --- |
| `list_note` 是否返回 `next_cursor` | 若实际存在则原样保留；缺失返回空字符串；`is_end` 为权威完成字段 | 待验证 |
| `list_notebook` 的版本增量语义 | API 方法接受可选 `version` 并原样返回 `next_version`/`need_update`；CLI 暂无入口 | 待验证 |
| 文档中两组 Notes 错误码差异 | 运行时透传非零 `code` 与 `msg`，不在批次 A 建立枚举 | 待上游澄清 |

不得用写入 smoke 验证本契约。只读 smoke 也需人工确认并且不得把真实 ID、正文或凭证写入 fixtures。

## Fixtures

`tests/fixtures/notes` 使用完整 wire envelope。内容来自 1.1.7 文档建模，不是真实账户抓取；固定使用 `note_test_*`、`folder_test_*`、固定时间戳、`example.com` 和无隐私 Unicode 示例。更新契约时必须同时更新此文档、fixture、测试和活动 skill。
