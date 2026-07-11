# 批次 A 详细实现计划：契约安全网与 Notes 迁移

> 编制日期：2026-07-11  
> 对应总计划：OPTIMIZATION_PLAN.md 的阶段 0、阶段 1 和 Notes 文档最小同步  
> 计划状态：已实施（2026-07-11，全量单元测试通过）  
> 生产依赖策略：不新增生产依赖

## 1. 批次目标

批次 A 解决两个紧密关联的问题：

1. 现有测试无法发现 IMA Notes API 从 1.1.2 到 1.1.7 的契约变化。
2. 当前 Notes 客户端仍使用旧端点、旧字段名和旧响应层级。

完成后，项目应具备一套不访问真实网络、基于脱敏响应 fixture 的 1.1.7 契约测试；Notes 的搜索、列表、笔记本、读取、创建和追加全部切换到 1.1.7；CLI 以 note_id 为正式术语，同时为现有 doc_id 用户提供明确的短期兼容层。

## 2. 范围边界

### 2.1 本批次包含

- 建立 Notes 1.1.7 契约裁决文档；
- 建立六个 Notes 接口的脱敏 wire fixtures；
- 增加 HTTP 基础契约测试；
- 增加 Notes API endpoint、payload 和响应解析测试；
- 迁移 Notes 六个接口；
- 迁移 doc_id/docid 到 note_id；
- 更新 Notes 数据模型与兼容属性；
- 落实写入前 UTF-8 可编码性检查；
- 过滤 Markdown 中的本地图片并报告；
- 更新 Notes CLI、KB add-note 交叉引用和 JSON 输出；
- 保留必要的 CLI/Python 兼容入口；
- 更新 README 和活动中的 Notes/CLI skill 文档；
- 修复批次 A 触及的 CLI 测试输出泄漏。

### 2.2 本批次不包含

- get_media_info、知识库原文读取或导出；
- 文件型 URL 下载和上传；
- COS 流式上传及上传补偿；
- 凭证目录和配置优先级重构；
- 完整错误层级、重试或全局 JSON Schema 重构；
- 全量 CLI 目录拆分；
- skills 目录的最终合并、删除或重新发布；
- CI、coverage 工具、lint、类型检查和发布流水线；
- Node.js 自更新逻辑或 CJS 运行时集成；
- 真实写入 API 的自动 smoke test。

这些项目继续由后续批次处理。批次 A 不应以“顺手重构”为理由扩大范围。

## 3. 当前问题

### 3.1 Notes endpoint 已过期

当前实现与 1.1.7 的差异：

| 能力 | 当前实现 | 1.1.7 目标 |
| --- | --- | --- |
| 搜索笔记 | search_note_book | search_note |
| 列出笔记本 | list_note_folder_by_cursor | list_notebook |
| 列出笔记 | list_note_by_folder_id | list_note |
| 读取正文参数 | doc_id | note_id |
| 追加参数 | doc_id | note_id |
| 创建/追加返回 | doc_id | note_id |

主要位置：

- src/ima_note_cli/notes_api.py:42-142
- src/ima_note_cli/notes_cli.py:63-83
- src/ima_note_cli/knowledge_api.py:184-200
- src/ima_note_cli/knowledge_cli.py:45-51

影响：真实服务若只接受 1.1.7，新旧端点和字段不兼容时会直接导致查询或写入失败。

### 3.2 响应结构已改变

搜索结果：

~~~text
旧：docs[].doc.basic_info.docid
新：search_note_infos[].note_book_info.note_id
~~~

笔记本：

~~~text
旧：note_book_folders[].folder.basic_info
新：note_folder_infos[]
~~~

笔记列表：

~~~text
旧：note_book_list[].basic_info.basic_info
新：note_book_list[]，每项直接是 NoteBookInfo
~~~

扩展字段：

~~~text
旧：folder_id、folder_name 位于旧 basic_info
新：note_ext_info.folder_id、note_ext_info.folder_name
~~~

高亮字段：

~~~text
旧：highlight_info
新：highlightInfo
~~~

当前解析器会在新响应下得到空字段或触发未包装异常。

### 3.3 当前模型与 1.1.7 不一致

SearchResult 当前以 doc_id 为主，并包含新版文档未定义的 status；同时缺少 cover_image。

FolderResult 当前解析旧的嵌套 basic_info，并保留新版未定义的 status。

迁移时需要同时兼顾：

- 新代码内部统一使用 note_id；
- 新 JSON 输出使用 note_id；
- 旧的 Python 使用者可能仍访问 SearchResult.doc_id；
- 现有 CLI 脚本可能读取 JSON 中的 doc_id；
- 现有 kb add-note 使用 --doc-id。

### 3.4 现有测试绕过了协议层

tests/test_cli.py 直接替换 NotesApiClient，因此只能证明：

- 命令分发正确；
- Fake Client 的返回值可以被打印；
- 部分参数被传给 Fake Client。

它不能证明：

- endpoint 名称正确；
- 请求字段正确；
- 1.1.7 的嵌套数据能被解析；
- 缺失 note_id 时会失败；
- HTTP 业务错误会被正确处理。

这是当前最大的质量缺口。

### 3.5 HTTP 层允许缺失 code

src/ima_note_cli/http.py 中 SUCCESS_CODE_VALUES 包含 None，因此不含 code 的响应可能被当作成功。

1.1.7 的标准响应具有明确的 code、msg 和 data。批次 A 至少需要收紧足以支撑契约测试的部分：

- code 必须存在；
- code 为 0 或兼容字符串 0 时成功；
- code 非 0 时使用 msg 抛 ApiError；
- 成功时 data 必须为对象；
- 非 JSON、非对象和错误 data 形状必须失败。

完整错误层级、重试和响应大小限制仍在后续批次。

### 3.6 写入安全规则未完整落实

1.1.7 规定：

- import_doc 和 append_doc 的字符串必须是合法 UTF-8；
- 本地图片不能写入 Notes；
- 网络图片可以保留；
- 被移除的本地图片必须告知用户。

当前代码只对文件使用 UTF-8 read_text，没有：

- 对直接传入字符串执行严格 UTF-8 编码测试；
- 捕获并解释孤立代理字符；
- 识别本地 Markdown 图片；
- 报告被过滤的图片；
- 在过滤后内容为空时停止写入。

### 3.7 CLI 和 JSON 存在兼容风险

受影响的用户接口：

- ima note get 的位置参数内部名为 doc_id；
- ima note append 的位置参数内部名为 doc_id；
- ima kb add-note 只接受 --doc-id；
- 搜索、列表、读取、创建、追加 JSON 均输出 doc_id；
- 人类输出显示 doc_id 或 Doc ID；
- README 和 skills 使用 your_doc_id。

若一次性删除 doc_id，会破坏现有脚本。若继续只输出 doc_id，又会让新契约和代码继续漂移。

### 3.8 1.1.7 自身仍有待裁决点

批次 A 必须记录而不能猜测：

1. list_note 请求有 cursor，但参考响应没有明确列出 next_cursor。
2. list_notebook 支持 version、next_version 和 need_update，当前 CLI 没有对应入口。
3. SearchResult 旧 status 字段在 1.1.7 中不存在。
4. highlightInfo 使用驼峰命名，与项目现有蛇形命名不同。
5. Notes SKILL 和 references 中的错误码段不完全一致。

## 4. 实现原则和已选策略

### 4.1 契约优先级

按以下顺序裁决：

1. 1.1.7 references/api.md 的请求和响应结构；
2. 1.1.7 notes/SKILL.md 的工作流规则；
3. 脱敏真实响应或受保护的只读 smoke 结果；
4. 旧 1.1.2 仅用于兼容分析，不作为新实现依据。

所有无法验证的差异写入 docs/API_CONTRACT_1_1_7.md，不在解析器里静默猜测多个互相冲突的结构。

### 4.2 note_id 为唯一内部主名称

- API 请求和解析使用 note_id；
- CLI Namespace 使用 note_id；
- 新模型字段使用 note_id；
- 人类输出显示 note_id；
- 新文档统一使用 note_id。

doc_id 只存在于明确标记的兼容层中。

### 4.3 CLI 兼容策略

位置参数命令的用户语法不变：

~~~text
ima note get NOTE_ID
ima note append NOTE_ID --content ...
~~~

仅把 argparse 内部 dest 和帮助文本改为 note_id。

kb add-note 采用两个互斥参数：

~~~text
--note-id NOTE_ID      正式参数
--doc-id NOTE_ID       兼容参数，标记 deprecated
~~~

两个参数最终都解析到同一个 note_id。若用户使用 --doc-id：

- 人类模式：向 stderr 输出弃用提示；
- JSON 模式：成功 JSON 中加入 warnings 数组，不污染 stdout 之外的机器输出。

### 4.4 JSON 兼容策略

批次 A 后的新 JSON 以 note_id 为正式字段，同时保留 doc_id 兼容字段一个版本周期：

~~~json
{
  "note_id": "note_xxx",
  "doc_id": "note_xxx"
}
~~~

规则：

- 两个字段必须始终相等；
- README 标记 doc_id 已弃用；
- 本批次不删除 doc_id；
- 删除时机由后续版本/发布计划决定；
- 新增测试锁定双字段行为，防止一边更新另一边遗漏。

### 4.5 Python API 兼容策略

SearchResult 保留导出名称，内部主字段改为 note_id：

- 提供只读 doc_id 兼容属性；
- 兼容构造路径可接受 note_id 或 doc_id；
- 两者同时传入且值不同时必须报错；
- 新代码和新测试只使用 note_id；
- api.py 继续导出 SearchResult 和 ImaNoteApiClient。

FolderResult 的 status 暂时保留为可选兼容字段，默认 None，不再用于逻辑。cover_image 添加到 Notes 条目模型。

完整地将 Notes 和 Knowledge 分页结果全部改成统一泛型模型，不属于本批次；批次 A 保持顶层返回结构与 CLI 的改动可控。

### 4.6 list_note 游标策略

在无法确认 next_cursor 前：

- is_end 是完成判断的权威字段；
- 若响应实际包含 next_cursor，则原样保留；
- 若不存在，兼容返回空字符串；
- 不根据输入 cursor 伪造下一个值；
- 契约文档明确记录此字段待只读 smoke 验证；
- 不在批次 A 增加依赖不明确游标的 --all 自动翻页。

### 4.7 本地图片处理策略

新增纯标准库的 Notes 内容预处理模块。

识别并移除：

- file:// URL；
- Windows 盘符路径；
- UNC 路径；
- POSIX 绝对路径；
- 以 ./、../、~/ 开头的路径；
- Markdown 图片目标中其他非 HTTP/HTTPS 的本地路径；
- HTML img 标签中的本地 src。

保留：

- http:// 图片；
- https:// 图片。

data URI 默认过滤，因为 1.1.7 只明确允许网络图片。

处理结果包含：

- 清洗后的 Markdown；
- 被移除的图片路径列表；
- warnings 列表。

若清洗后只有空白，则在发起 API 请求前失败。

### 4.8 不新增生产依赖

fixture、mock、Markdown 图片过滤和 UTF-8 校验均使用标准库和 unittest。

若实现过程中发现必须引入生产依赖，停止该子项并先请求确认。

## 5. 详细实施步骤

### A0.1 建立契约裁决文档

新增 docs/API_CONTRACT_1_1_7.md。

内容：

- 六个 Notes endpoint；
- 请求字段、必填性和限制；
- 响应结构与模型映射；
- note_id 兼容规则；
- list_note 游标歧义；
- list_notebook version 字段策略；
- 错误处理原则；
- fixture 来源和脱敏规则；
- 已确认项、待验证项和最终裁决状态。

该文档是实现和测试的唯一迁移依据，避免代码、测试和 README 各自解释 1.1.7。

### A0.2 建立脱敏 wire fixtures

新增目录 tests/fixtures/notes。

计划文件：

- README.md：来源、脱敏和更新规则；
- search_note_success.json；
- search_note_empty.json；
- list_notebook_success.json；
- list_notebook_empty.json；
- list_note_success.json；
- list_note_empty.json；
- get_doc_content_success.json；
- import_doc_success.json；
- append_doc_success.json；
- business_error.json；
- malformed_missing_code.json；
- malformed_data_array.json。

fixture 使用完整 wire envelope：

~~~json
{
  "code": 0,
  "msg": "success",
  "data": {}
}
~~~

fixture 要求：

- 不含真实凭证；
- ID 使用 note_test_001、folder_test_001；
- 正文使用无隐私的示例文本；
- URL 使用 example.com；
- 时间戳固定；
- 字段覆盖空值、可选值和正常 Unicode；
- 不使用随机值，确保测试稳定。

### A0.3 增加 fixture 加载辅助

新增 tests/_fixtures.py：

- 使用 pathlib 定位 fixture；
- 使用 json 读取；
- 返回完整 envelope；
- 提供提取 data 的小型辅助；
- 对 fixture 不是对象时立即让测试失败。

不把 fixture loader 放入生产包。

### A0.4 增加 HTTP 基础契约测试

新增 tests/test_http.py。

覆盖：

- code=0 且 data 为对象时返回 data；
- code 为字符串 0 的兼容行为；
- code 非 0 时抛 ApiError，消息包含后端 msg；
- 缺少 code 时失败；
- data 为数组或字符串时失败；
- 非 JSON 响应失败；
- 顶层不是对象时失败；
- HTTPError 转为 ApiError；
- URLError 转为 ApiError；
- TimeoutError 转为 ApiError；
- Content-Type 和两个凭证 header 正确；
- 请求 Body 是 UTF-8 JSON 字节；
- 测试中不会访问真实网络。

对 src/ima_note_cli/http.py 只做通过这些基础契约测试所需的最小调整：

- 从成功集合移除 None；
- 明确缺少 code 的错误；
- 保留 ApiError 类型；
- 不在本批次引入重试、全局错误层级或响应大小限制。

### A0.5 增加 Notes API 契约测试

新增 tests/test_notes_api.py。

使用 RecordingNotesClient 或 mock transport：

- 记录 endpoint；
- 记录 payload；
- 返回 fixture 的 data；
- 分别断言请求和解析。

搜索测试：

- endpoint 为 search_note；
- title 搜索构造 query_info.title；
- content 搜索构造 query_info.content；
- start/end 差值不超过 20；
- sort_type 正确；
- 解析 search_note_infos；
- 解析 note_book_info；
- 解析 note_ext_info；
- 解析 highlightInfo.doc_title；
- 解析 cover_image；
- 缺少 note_id 时失败；
- search_note_infos 不是数组时失败。

笔记本测试：

- endpoint 为 list_notebook；
- 首页 cursor 为字符串 0；
- limit 范围为 1–20；
- version 仅在提供时发送；
- 解析 note_folder_infos；
- 解析 next_cursor、next_version、need_update；
- 空列表行为稳定。

笔记列表测试：

- endpoint 为 list_note；
- 请求包含 folder_id、sort_type、cursor、limit；
- 空 folder_id 表示全部笔记；
- folder_id 为字符串 0 时拒绝；
- 解析扁平 note_book_list；
- is_end 正确；
- next_cursor 缺失时返回空字符串；
- 可选 next_cursor 存在时保留。

读取测试：

- endpoint 为 get_doc_content；
- payload 使用 note_id；
- target_content_format 固定为 0；
- 返回 note_id 和 content；
- 空 note_id 在发请求前拒绝。

创建测试：

- endpoint 为 import_doc；
- content_format 固定为 1；
- content 非空；
- folder_id 仅在非空时发送；
- 返回 note_id；
- 返回缺少 note_id 时失败。

追加测试：

- endpoint 为 append_doc；
- payload 使用 note_id；
- content_format 固定为 1；
- 空 note_id/content 在发请求前拒绝；
- 返回 note_id；
- 返回缺少 note_id 时失败。

### A0.6 保留红绿验证过程，但提交必须保持绿色

开发过程：

1. 先写新契约测试，确认旧实现会失败；
2. 记录失败点；
3. 修改实现；
4. 提交前保证所有测试恢复为绿色。

不建议提交一个主分支必然红灯的“只有失败测试”状态。测试和使其通过的最小实现可在同一可审查提交中出现。

### A1.1 迁移 Notes 模型

修改 src/ima_note_cli/notes_api.py。

SearchResult：

- note_id：正式 ID；
- title；
- summary；
- folder_id；
- folder_name；
- create_time；
- modify_time；
- cover_image；
- highlight_title；
- status：兼容字段，可选且默认 None；
- doc_id：只读兼容属性。

FolderResult：

- folder_id；
- name；
- note_number；
- create_time；
- modify_time；
- folder_type；
- parent_folder_id；
- status：兼容字段，可选且默认 None。

模型解析不得使用 str(None)；空值应得到空字符串或 None，具体规则由字段类型决定。

### A1.2 迁移 Notes 六个客户端方法

修改 src/ima_note_cli/notes_api.py。

search_notes：

- endpoint 改为 search_note；
- 参数校验：query 去除首尾空白后不能为空；
- limit 为 1–20；
- start 不得为负；
- search_type 和 sort_type 必须是支持值；
- 解析 search_note_infos。

get_doc_content：

- 参数名改为 note_id；
- payload 使用 note_id；
- 返回兼容结构同时包含 note_id 和 doc_id。

list_folders：

- endpoint 改为 list_notebook；
- 增加可选 version 参数；
- 解析 note_folder_infos；
- 返回 next_version 和 need_update。

list_notes：

- endpoint 改为 list_note；
- 增加 sort_type，默认 0；
- limit 为 1–20；
- 解析扁平 note_book_list；
- is_end 为主要终止标记。

create_note：

- endpoint 仍为 import_doc；
- 严格检查 content；
- 返回 note_id/doc_id 兼容字段。

append_note：

- endpoint 仍为 append_doc；
- payload 改为 note_id；
- 严格检查 note_id 和 content；
- 返回 note_id/doc_id 兼容字段。

### A1.3 新增 Notes 内容预处理模块

新增 src/ima_note_cli/notes_content.py。

建议公开函数：

~~~text
prepare_note_markdown(content) -> PreparedNoteMarkdown
ensure_valid_utf8(value, field_name) -> None
~~~

PreparedNoteMarkdown 建议包含：

- content；
- removed_local_images；
- warnings。

处理顺序：

1. 确认输入是字符串；
2. 严格执行 UTF-8 encode；
3. 识别并移除本地图片；
4. 再次检查结果；
5. 清洗后为空则失败；
6. 返回内容和诊断信息。

不得：

- 修改网络图片 URL；
- 读取本地图片；
- 上传本地图片；
- 对 Markdown 正文做无关格式化；
- 使用 errors=ignore 静默丢弃非法字符。

### A1.4 集成创建和追加工作流

修改 src/ima_note_cli/notes_cli.py。

创建：

~~~text
读取 --content/--file
  → compose_markdown
  → prepare_note_markdown
  → client.create_note
  → 输出结果和 warnings
~~~

追加：

~~~text
读取 --content/--file
  → prepare_note_markdown
  → client.append_note
  → 输出结果和 warnings
~~~

文件读取发生 UnicodeDecodeError 时：

- 显示文件必须是 UTF-8 的明确错误；
- 不发 API 请求；
- 不自动猜测或转码；
- 自动编码探测留待用户明确提出后再设计。

输出规则：

- 人类模式：成功信息写 stdout，图片过滤警告写 stderr；
- JSON 模式：stdout 只输出 JSON，warnings 和 removed_local_images 放入 JSON；
- 成功 JSON 仍包含 note_id 和 doc_id 兼容字段。

### A1.5 迁移 Notes CLI 标识

修改 src/ima_note_cli/notes_cli.py。

- get_parser 位置参数 dest 改为 note_id；
- append_parser 位置参数 dest 改为 note_id；
- 帮助文本改为 Note ID；
- handle_get、handle_append 使用 note_id；
- 人类输出将 Doc ID/doc_id 改为 note_id；
- search_result_to_dict 输出 note_id 和 doc_id；
- create、append、get JSON 输出双字段；
- 列表输出以 note_id 为主；
- note list 增加可选 --sort，映射现有 SORT_TYPE_MAP；
- 所有 limit 在发请求前校验 1–20。

命令表面语法保持不变。

### A1.6 迁移 KB add-note 交叉引用

修改：

- src/ima_note_cli/knowledge_api.py；
- src/ima_note_cli/knowledge_cli.py。

KnowledgeBaseApiClient.add_note：

- Python 参数改为 note_id；
- note_info.content_id 继续使用该 ID；
- 返回 note_id 和 doc_id 兼容字段。

CLI：

- 新增 --note-id；
- 保留 --doc-id 兼容参数；
- 两者互斥且必须提供一个；
- title 默认值使用 note_id；
- 人类输出显示 note_id；
- JSON 输出包含双字段；
- 使用旧参数时输出兼容警告。

该改动仅迁移 ID 术语，不改变 add_knowledge 的 media_type=11 流程。

### A1.7 维护公共导出兼容性

修改 src/ima_note_cli/api.py。

- 继续导出 NotesApiClient；
- 继续保留 ImaNoteApiClient 别名；
- 继续导出 SearchResult、FolderResult；
- 若新增 PreparedNoteMarkdown，不默认从 api.py 暴露，除非确定它属于公共 API；
- 增加兼容行为测试，确保旧导入路径仍工作。

本批次不重命名 Python 包或 console entry point。

### A1.8 更新现有 CLI 测试

修改 tests/test_cli.py。

FakeNotesClient：

- 参数和记录字段改为 note_id；
- 默认返回同时含 note_id/doc_id；
- SearchResult 使用 note_id；
- 保留一组 doc_id 兼容断言。

增加或更新：

- 搜索人类输出显示 note_id；
- 搜索 JSON 包含相等的 note_id/doc_id；
- list JSON 使用新字段；
- get/append 位置参数语法不变；
- create/append JSON 双字段；
- kb add-note --note-id；
- kb add-note --doc-id 兼容路径；
- 兼容警告不会污染 JSON stdout；
- 本地图片 warning 行为；
- 所有触及的测试捕获 stdout/stderr。

### A1.9 增加内容预处理测试

新增 tests/test_notes_content.py。

测试矩阵：

- 普通 Unicode Markdown 不变；
- HTTP 图片保留；
- HTTPS 图片保留；
- file:// 图片移除；
- Windows 盘符图片移除；
- UNC 图片移除；
- POSIX 绝对路径图片移除；
- ./、../、~/ 图片移除；
- HTML img 本地 src 移除；
- HTML img 网络 src 保留；
- data URI 移除；
- 混合图片只移除本地项；
- removed_local_images 顺序稳定；
- 孤立代理字符被拒绝；
- 过滤后为空被拒绝；
- 文本中的普通路径不是图片时不误删。

### A1.10 增加 Knowledge add-note 聚焦测试

新增 tests/test_knowledge_api.py，或在已有测试结构中增加独立类。

仅覆盖批次 A 交叉影响：

- add_note 使用 note_id；
- payload 的 note_info.content_id 正确；
- media_type 固定为 11；
- folder_id 为空时省略；
- 返回 note_id/doc_id 相等；
- 空 note_id 在发请求前拒绝。

其他 Knowledge API 测试属于后续批次。

### A1.11 最小文档同步

修改 README.md：

- 功能说明改为 note_id；
- get、append、kb add-note 示例改用 note_id；
- 说明 --doc-id 是兼容参数；
- 说明 JSON 暂时同时包含 note_id/doc_id；
- 增加本地图片过滤规则；
- 更新项目结构中的 notes_content.py 和新测试。

修改 skills/ima-note/SKILL.md：

- 更新六个 endpoint；
- 更新 note_id；
- 更新新响应层级；
- 同步本地图片和 UTF-8 规则。

修改 skills/ima-note/references/api.md：

- 同步 1.1.7 Notes 请求/响应契约；
- 保留上游来源和版本说明。

修改 skills/ima-note-cli/SKILL.md：

- 更新命令示例；
- 使用 note_id；
- 说明 --doc-id 兼容期。

明确不修改：

- skills/ima-skills-1.1.2 的历史内容；
- ima-skills-1.1.7 (1) 的目录组织；
- skills 最终发布方式。

旧版目录的归档、合并和删除留在批次 D。

## 6. 涉及文件

### 6.1 新增文件

| 文件 | 用途 |
| --- | --- |
| BATCH_A_IMPLEMENTATION_PLAN.md | 本详细计划 |
| docs/API_CONTRACT_1_1_7.md | Notes 1.1.7 契约裁决 |
| src/ima_note_cli/notes_content.py | UTF-8 和本地图片预处理 |
| tests/_fixtures.py | 测试 fixture 加载 |
| tests/test_http.py | HTTP 基础契约测试 |
| tests/test_notes_api.py | Notes endpoint/payload/解析测试 |
| tests/test_notes_content.py | Markdown/UTF-8 测试 |
| tests/test_knowledge_api.py | add-note 的 note_id 聚焦测试 |
| tests/fixtures/notes/README.md | fixture 来源与脱敏规则 |
| tests/fixtures/notes/*.json | 1.1.7 脱敏 wire fixtures |

### 6.2 修改文件

| 文件 | 计划改动 |
| --- | --- |
| src/ima_note_cli/http.py | 最小收紧 code/data 契约 |
| src/ima_note_cli/notes_api.py | 六个 endpoint、模型、解析、note_id |
| src/ima_note_cli/notes_cli.py | 参数、内容预处理、输出和兼容 JSON |
| src/ima_note_cli/knowledge_api.py | add_note 参数与返回 ID 迁移 |
| src/ima_note_cli/knowledge_cli.py | --note-id 与 --doc-id 兼容 |
| src/ima_note_cli/api.py | 公共导出兼容 |
| tests/test_cli.py | Fake Client、字段和兼容用例 |
| README.md | note_id、图片规则和兼容说明 |
| skills/ima-note/SKILL.md | 活动 Notes skill 迁移 |
| skills/ima-note/references/api.md | 活动 Notes API reference 迁移 |
| skills/ima-note-cli/SKILL.md | CLI 示例与兼容说明 |
| OPTIMIZATION_PLAN.md | 链接本详细计划 |

### 6.3 预计无需修改

- pyproject.toml；
- uv.lock；
- config.py；
- knowledge_upload.py；
- 知识库 URL/媒体/上传相关实现；
- skills/ima-skills-1.1.2 历史快照；
- 1.1.7 下载目录中的原始文件。

若实施中需要修改这些文件，应先说明原因并重新确认是否仍属于批次 A。

## 7. 验收矩阵

### 7.1 API 契约

- [x] search_notes 调用 search_note；
- [x] list_folders 调用 list_notebook；
- [x] list_notes 调用 list_note；
- [x] get_doc_content 使用 note_id；
- [x] append_note 使用 note_id；
- [x] import_doc/append_doc 解析 note_id；
- [x] 搜索解析 search_note_infos[].note_book_info；
- [x] 笔记本解析 note_folder_infos[]；
- [x] 笔记列表解析扁平 note_book_list[]；
- [x] note_ext_info 和 highlightInfo 正确解析；
- [x] 必填 note_id 缺失时明确失败；
- [x] 所有 limit 和 start/end 限制在请求前验证。

### 7.2 HTTP 安全网

- [x] code=0 正确解包；
- [x] code 非 0 显示后端 msg；
- [x] 缺少 code 不再视为成功；
- [x] 非 JSON、非对象和错误 data 形状明确失败；
- [x] HTTP、URL 和 timeout 错误被转换为 ApiError；
- [x] 请求 Body 是 UTF-8 字节；
- [x] 测试不会发出真实网络请求。

### 7.3 写入安全

- [x] 直接输入和文件内容在写入前通过严格 UTF-8 检查；
- [x] 孤立代理字符不会被发送；
- [x] 本地图片被移除；
- [x] HTTP/HTTPS 图片保留；
- [x] 被移除路径可被用户看到；
- [x] JSON 成功输出不混入普通警告文本；
- [x] 过滤后空内容不会调用 API；
- [x] append 必须具有明确 note_id。

### 7.4 CLI 兼容

- [x] ima note get NOTE_ID 语法保持可用；
- [x] ima note append NOTE_ID 语法保持可用；
- [x] ima-note 旧 console entry point 保持可用；
- [x] ima kb add-note --note-id 可用；
- [x] ima kb add-note --doc-id 在兼容期可用；
- [x] 使用 --doc-id 时有清晰弃用信息；
- [x] 人类输出使用 note_id；
- [x] JSON 同时包含相等的 note_id/doc_id；
- [x] SearchResult.doc_id 兼容属性可用；
- [x] api.py 既有导入路径保持可用。

### 7.5 文档一致性

- [x] 活动源码和活动文档不再使用旧 endpoint；
- [x] README 示例使用 note_id；
- [x] skills/ima-note 与 1.1.7 Notes 契约一致；
- [x] skills/ima-note-cli 说明兼容期；
- [x] 旧 endpoint 只允许出现在历史 1.1.2 快照、迁移说明或测试旧值中；
- [x] fixture 来源、版本和脱敏规则有记录。

### 7.6 测试与工作区

- [x] 全部既有测试通过；
- [x] 所有新增测试通过；
- [x] 测试输出没有意外 CLI 文本泄漏；
- [x] 不需要真实凭证；
- [x] 不访问真实 IMA/COS；
- [x] 不新增生产依赖；
- [x] 不修改 .env；
- [x] 不修改批次外逻辑；
- [x] Git diff 无行尾和空白错误。

## 8. 验证命令

实施完成后至少执行：

~~~powershell
uv run python -m unittest tests.test_http -v
uv run python -m unittest tests.test_notes_api -v
uv run python -m unittest tests.test_notes_content -v
uv run python -m unittest tests.test_knowledge_api -v
uv run python -m unittest tests.test_cli -v
uv run python -m unittest discover -s tests -v
uv run python -m ima_note_cli --help
uv run python -m ima_note_cli note --help
uv run python -m ima_note_cli kb add-note --help
rtk rg -n "search_note_book|list_note_folder_by_cursor|list_note_by_folder_id|docid" src README.md skills/ima-note skills/ima-note-cli
rtk git diff --check
rtk git status --short
~~~

旧 endpoint 搜索允许命中：

- 明确的迁移说明；
- 兼容性测试；
- skills/ima-skills-1.1.2 历史快照。

不应命中活动生产实现。

## 9. 可选的受保护只读 smoke

单元测试仍是批次 A 的必需门禁。若有可安全使用的测试账户，可在人工确认后额外执行只读 smoke：

~~~text
ima auth
ima note search "test" --limit 1 --json
ima note folders --limit 1 --json
ima note list --limit 1 --json
~~~

规则：

- 不在 CI 中使用真实凭证；
- 不记录响应正文；
- 不执行 import_doc；
- 不执行 append_doc；
- 不将真实 ID 写入 fixture；
- smoke 失败先记录原始响应形状，再决定是否更新契约裁决。

创建和追加的真实验证属于有副作用操作，必须使用专门测试账户并单独获得确认，不作为批次 A 自动验收项。

## 10. 实施顺序与提交切片

### A-1：契约和 fixtures

- docs/API_CONTRACT_1_1_7.md；
- tests/fixtures/notes；
- tests/_fixtures.py；
- 契约问题裁决。

### A-2：HTTP 与 Notes API 红绿迁移

- tests/test_http.py；
- tests/test_notes_api.py；
- http.py 最小收紧；
- notes_api.py endpoint、payload、模型和解析迁移。

### A-3：内容安全与 CLI 兼容

- notes_content.py；
- tests/test_notes_content.py；
- notes_cli.py；
- knowledge_api.py；
- knowledge_cli.py；
- api.py；
- test_cli.py；
- test_knowledge_api.py。

### A-4：活动文档同步和总体验证

- README.md；
- skills/ima-note；
- skills/ima-note-cli；
- OPTIMIZATION_PLAN.md 链接；
- 全量测试和旧 endpoint 搜索。

每个提交切片在进入下一片前应保持可运行。若红绿过程在本地短暂失败，最终提交不能留下预期失败测试。

## 11. 主要风险与应对

### 风险 1：1.1.7 文档与真实响应仍不同

应对：

- wire fixture 与契约裁决分离；
- 未确认字段保持可选；
- 关键 ID 和结构保持严格；
- 可选只读 smoke 只用于验证形状；
- 不在解析器中同时支持多个未经证明的响应树。

### 风险 2：doc_id 兼容导致长期双轨

应对：

- 内部只使用 note_id；
- doc_id 仅存在于集中兼容出口；
- 文档明确弃用；
- 测试保证双字段相等；
- 后续发布计划设定删除版本。

### 风险 3：Markdown 图片过滤误删内容

应对：

- 只处理图片语法，不处理普通链接或普通路径文本；
- 网络图片保留；
- 建立 Windows、POSIX、UNC、相对路径和 HTML 测试矩阵；
- 返回 removed_local_images 供用户核对。

### 风险 4：严格解析使此前被吞掉的错误暴露

这是预期行为。关键字段缺失应失败，而不是显示“成功但 ID 为空”。错误信息必须包含 endpoint 和缺失字段，便于定位。

### 风险 5：批次范围扩张

应对：

- 不做通用 CLI 目录重构；
- 不做上传和 URL 工作流；
- 不引入新依赖；
- 批次外问题记录到总计划，不在当前实现中插入半成品。

## 12. 完成定义

批次 A 只有在以下条件同时满足时才算完成：

1. 1.1.7 Notes 契约已记录且所有待裁决项有状态。
2. 六个 Notes endpoint 的请求与响应都有 fixture 驱动测试。
3. 活动生产代码不再调用三个旧 Notes endpoint。
4. API 和 CLI 内部以 note_id 为主。
5. 现有 doc_id 用户有明确、经过测试的兼容路径。
6. 本地图片和非法 UTF-8 不会被发送到 IMA。
7. HTTP 基础契约能发现缺失 code 和错误 data 形状。
8. 全部单元测试通过且不访问真实网络。
9. README 和活动 skill 与实现一致。
10. 未新增生产依赖，未越界修改后续批次功能。

完成批次 A 后，再进入批次 B 的 HTTP/配置全面加固和 get_media_info 实现。
