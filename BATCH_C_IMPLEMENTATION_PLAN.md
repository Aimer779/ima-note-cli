# 批次 C 详细实现计划：URL、上传和 CLI 重构

> 编制日期：2026-07-12  
> 对应总计划：OPTIMIZATION_PLAN.md 的阶段 3 中用户 URL 检测与下载再上传、阶段 4、阶段 5  
> 实施基线：批次 A/B 已实施，当前 `uv run python -m unittest discover -s tests -v` 为 103/103 通过  
> 计划状态：已实施（2026-07-12）  
> 生产依赖策略：默认不新增生产依赖，继续使用 Python 标准库；若压缩音频时长检测确需第三方库，必须另行确认

## 1. 批次目标

批次 C 解决三组已经互相耦合的问题：

1. 用户传给 `ima kb add-url` 的地址目前只能做静态后缀判断，不能可靠地区分页、微信公众号文章和可下载文件。
2. 当前上传流程会一次性把文件读入内存，缺少文件状态复核、凭证时效、COS key 规范化、重名改名和阶段性失败结果。
3. CLI 注册、校验、业务编排、人类输出和 JSON 序列化混在大型模块中，阻碍 URL 与批量上传流程安全落地。

完成后，以下工作流应成为同一套可测试服务：

~~~text
用户 URL
  -> 安全探测
  -> 网页 / 微信文章 ----------------> import_urls
  -> 文件型 URL -> 有界临时下载 -----> UploadService

本地文件 --------------------------------> UploadService

UploadService
  -> 文件预检
  -> 批量重名检查
  -> 冲突策略
  -> create_media
  -> 流式 COS PUT
  -> 文件状态复核
  -> add_knowledge
~~~

CLI 则只负责：

- 注册命令和参数；
- 将参数转换为类型明确的请求；
- 调用服务；
- 把结构化结果交给统一输出层。

本批次不会通过重试、静默替换或猜测类型来掩盖不确定性。每个已经发生远程副作用的阶段都必须在结果中可辨识，同时不得泄露 URL 查询参数、IMA 凭证、COS 临时凭证、签名或本地临时路径。

## 2. 范围边界

### 2.1 本批次包含

- 对用户输入 URL 执行语法、协议、目标主机和重定向安全校验；
- 支持 HEAD 探测，并在服务端不支持或信息不足时使用无正文消费的受限 GET 探测；
- 结合最终 URL、Content-Type、Content-Disposition 和已知 URL 模式判定网页或文件；
- 明确识别微信公众号文章；
- 明确拒绝 file URL、Bilibili 视频、YouTube 视频和不支持的内容类型；
- 为文件型 URL 推断并清洗安全文件名；
- 将文件型 URL 流式下载到随机临时目录；
- 在响应头和实际读取两个层面限制下载大小；
- 无论成功、失败或中断都清理临时目录；
- 把下载后的文件交给与本地文件完全相同的上传服务；
- 抽取独立 UploadService；
- 将 COS PUT 改为固定 Content-Length 的低内存流式传输；
- 上传前、打开文件后、上传完成后复核文件身份、大小和修改状态；
- 校验 COS 凭证字段、开始时间、过期时间、官方域名和对象 key；
- 将上传超时默认值调整为 300 秒并允许命令行配置；
- 实现 `--on-conflict error|rename`，默认 error；
- 对 rename 结果再次执行服务端重名检查；
- 保证 add_knowledge.title、file_info.file_name 和 create_media.file_name 使用同一个最终文件名；
- COS 失败或文件发生变化后绝不调用 add_knowledge；
- add_knowledge 失败时返回可诊断但不含密钥的孤立 media 状态；
- 让 add-url 的网页导入结果、文件上传结果和本地分类失败统一为输入顺序稳定的逐项结果；
- 对部分成功返回稳定 JSON 和专用非零退出码；
- 允许 add-file 重复传入 `--file`，并在真正上传前一次性完成批量重名检查；
- 将命令处理器改为返回 CommandResult，不再捕获 stdout 后反向解析 JSON；
- 分离命令注册、业务服务、共享校验、分页收集和输出；
- 让所有游标或 offset 分页命令支持统一的 `--all` 与最大页数保护；
- 保留现有命令名称、单页默认行为、JSON 顶层业务字段和 ima-note 兼容入口；
- 用明确类型替换已知的 object、getattr 和无约束 dict 编排；
- 更新 README、活动 CLI skill、契约文档和离线测试。

### 2.2 本批次不包含

- 删除、合并或重新发布现有 skills 目录；
- 将上游 ima-skills-1.1.7 (1) 目录改造成正式包内容；
- CI、lint、类型检查、coverage、wheel 安装和发布流水线；
- 新增任意 IMA Base URL、代理 API 或非官方 IMA 服务端；
- 把 IMA 长期凭证、COS 临时凭证或用户 Cookie 转发到用户 URL；
- 自动登录、处理需要浏览器会话的下载页或绕过反爬机制；
- 支持 FTP、SFTP、data URL、file URL 或自定义协议；
- 支持 Bilibili、YouTube、本地 HTML 和视频上传；
- 静默替换知识库中已有同名文件；
- 删除已经创建但未成功注册的远端 media；1.1.7 没有提供对应删除接口；
- 断点续传、多分片 COS 上传或并行上传；
- 对 COS PUT 或 add_knowledge 自动重试；
- 自动猜测未知二进制文件的真实格式；
- 为 MP3、M4A、AAC 引入第三方音频解析依赖；
- 通用的知识库名、文件夹名和笔记标题自动解析；
- 真实账户写入 smoke test作为自动验收的一部分；
- 批次 D 的 canonical skill、许可证、版本、打包和发布工作。

### 2.3 与批次 B 的边界

批次 B 已完成：

- get_media_info；
- 笔记型媒体跨模块读取；
- IMA 返回的受控媒体 URL 读取和导出；
- 媒体 URL allowlist 与临时 header 的重定向保护；
- 统一错误、退出码、JSON envelope、配置和严格协议解析。

批次 C 新增的是“用户主动提供的任意公网 HTTP(S) URL”。它与批次 B 的媒体 URL 客户端不能共用信任模型：

- 批次 B 的 SourceHttpClient 只访问 ima.qq.com 或 myqcloud.com，并可能携带 IMA 返回的临时 headers；
- 批次 C 的 RemoteHttpClient 访问经过公网地址校验的用户 URL，永远不携带 IMA 或 COS 凭证；
- 两者可以共享纯函数级的 header、MIME 和大小工具，但不能共享 opener、redirect handler 或默认 headers。

## 3. 当前问题

### 3.1 add-url 只按路径后缀拒绝文件型 URL

当前 knowledge_cli.validate_urls 会检查 URL path 的扩展名，并提示用户自行下载后使用 add-file。

问题：

- 无法识别没有扩展名但 Content-Type 为 application/pdf 的下载；
- 无法识别 Content-Disposition 给出的真实文件名；
- 无法处理 arxiv、GitHub raw 和重定向后的文件地址；
- 会把带 .pdf 路径但实际返回 HTML 的地址误判；
- 与 1.1.7 明确要求的自动分流不一致；
- URL 解析和业务路由仍在 CLI 模块中。

### 3.2 当前没有适用于用户 URL 的网络安全边界

直接对任意用户 URL 发起请求会引入 SSRF 和凭证泄露风险：

- localhost、回环、链路本地、私网和保留地址可能被访问；
- 域名可以先解析到公网、连接时再次解析到内网；
- 重定向可能从公网跳到内网；
- URL 可以包含 userinfo、控制字符或非默认端口；
- 系统代理可能改变实际连接目标；
- 异常消息可能回显带 token 的完整查询字符串。

批次 B 的媒体 allowlist 不能直接用于这里，因为用户 URL 本来就不局限于 IMA/COS 域名。

### 3.3 URL 探测规则尚未形成可测试决策表

需要明确：

- HEAD 失败时何时回退 GET；
- Content-Type、Content-Disposition、最终 URL path 冲突时谁优先；
- application/octet-stream 如何处理；
- 微信、Bilibili 和 YouTube 在重定向前后如何识别；
- 未知 MIME 是拒绝、网页导入还是文件下载；
- 服务端缺少 Content-Type 时能否仅凭扩展名继续。

若没有固定决策表，同一个 URL 会在不同代码路径得到不同处理。

### 3.4 文件型 URL 缺少有界下载和临时文件清理

项目当前没有用户 URL 下载服务，因此也没有：

- Content-Length 预检；
- 读取过程中的硬上限；
- Content-Length 一致性校验；
- 随机临时目录；
- 安全文件名清洗；
- 中断和异常清理；
- 下载后的类型二次预检；
- 不泄露临时路径的错误模型。

### 3.5 import_urls 部分失败仍返回退出码 0

ImportUrlResult.ret_code 已被解析，但 handle_add_url 无论结果如何都返回 0。

这会导致：

- 自动化无法判断是否所有 URL 都成功；
- 人类输出和 JSON 对同一结果缺少统一状态；
- 混合网页与文件型 URL 后无法表达逐项阶段；
- 服务端部分失败、下载失败和上传失败无法放在同一结果模型中。

### 3.6 COS 上传会一次性把文件读入内存

knowledge_upload.upload_to_cos 当前调用 Path.read_bytes。

后果：

- 200 MiB 文件会额外占用约 200 MiB 内存；
- 文件越大，内存峰值和复制成本越高；
- 无法在传输期间检测短读或文件变化；
- 与总计划“200 MB 文件不一次性载入内存”的验收标准冲突。

### 3.7 文件预检仍缺少关键边界

当前 inspect_upload_file 已检查扩展名、MIME 和大小，但仍未完整覆盖：

- 空文件；
- 文件名最长 1024 字符；
- 控制字符、路径分隔符和危险文件名；
- stat 与真正打开文件之间发生替换；
- 上传过程中大小或 mtime 改变；
- WAV 音频超过 2 小时；
- 多文件时的输入内重名。

### 3.8 COS 凭证时效和 key 未完整校验

当前已有：

- bucket_name 与 region 的 DNS label 校验；
- 固定 myqcloud.com HTTPS origin；
- secret 字段 repr 隐藏。

仍缺少：

- start_time 与 expired_time 的相对关系；
- 凭证是否尚未生效或已经过期；
- 上传前剩余有效期是否过短；
- cos_key 为空、绝对 URL、反斜杠、控制字符、查询串或路径穿越；
- 用于签名的 pathname 与实际请求 path 是否完全一致；
- custom_domain 明确忽略的回归测试。

### 3.9 重名策略只有失败，没有 rename

当前流程在 is_repeated=true 时立即抛 InputError。

缺少：

- 用户显式选择保留两者的命令参数；
- 时间戳文件名生成；
- 多个同名输入的稳定后缀；
- 改名后再次询问服务端；
- 最终文件名贯穿 create_media、COS、file_info 和 title 的不变量；
- 批量上传在任何 create_media 前完成一次重名检查。

### 3.10 阶段性失败没有结构化结果

可能发生：

- create_media 成功、COS 失败；
- COS 成功、文件被修改，因此不能 add_knowledge；
- COS 成功、add_knowledge 失败，留下孤立 media；
- 多项任务中前几项成功，后续项失败；
- URL 下载成功，但本地预检失败。

当前异常只描述最终错误，无法稳定表达 stage、media_id、是否可能存在孤立对象和未执行项。

### 3.11 CLI 通过打印再解析 JSON 实现统一 envelope

cli._run_handler 会：

1. 捕获 handler 的 stdout/stderr；
2. 要求 handler 在 JSON 模式打印内部 JSON；
3. 再 json.loads；
4. 最后包一层公共 envelope。

问题：

- 业务处理器必须知道 as_json；
- 人类输出和机器输出重复实现；
- 任意调试打印都会变成 internal_error；
- handler 的返回值只剩 int，无法表达 partial；
- 测试不得不围绕 stdout，而不是业务结果；
- 服务层很难独立复用。

### 3.12 CLI 模块职责和类型仍然过重

当前：

- knowledge_cli 约 500 行；
- notes_cli 约 400 行；
- cli 同时处理 parser、凭证、依赖构造、输出捕获和 auth 展示；
- add_kb_subcommands 与 add_note_subcommands 使用 argparse 私有类型注解；
- path_node_to_dict、import_url_result_to_dict 使用 object/getattr；
- 多个 API 方法返回 dict[str, Any]，服务编排依赖字符串键。

### 3.13 校验逻辑重复且层级不清

limit、URL、文件、ID 和 cursor 校验分别出现在：

- CLI handler；
- API client；
- knowledge_upload；
- security。

CLI 需要尽早给出友好错误，API client 又必须保护公共 Python 调用；但两层目前没有共享纯函数，容易出现上限或错误文案漂移。

### 3.14 分页仍依赖用户手动复制 cursor

当前分页命令只取一页，缺少：

- 统一 --all；
- 最大页数；
- cursor 循环检测；
- is_end=false 但 next_cursor 为空的协议保护；
- offset 搜索无进展保护；
- 多页结果去重和稳定顺序；
- 达到保护上限时的 partial 结果。

### 3.15 JSON 的成功、空、部分成功语义尚未冻结

批次 B 已固定公共字段，但没有：

- status；
- partial 的结果与 error 共存规则；
- 批量计数；
- 单项 stage；
- 分页元数据；
- schema 的兼容承诺文档。

## 4. 实现原则和已选策略

### 4.1 保持兼容、先拆边界再迁移行为

必须保持：

- ima、ima-note 两个入口；
- 现有命令和参数名称；
- add-file 单个 --file 的调用方式；
- 默认只取一页；
- JSON schema_version=1；
- 已存在的顶层业务字段；
- --doc-id 的弃用兼容；
- api.py 中现有公共导出。

允许的兼容扩展：

- --file 可以重复；
- add-url 和 add-file 新增 --on-conflict；
- 新增 --download-timeout、--upload-timeout；
- 分页命令新增 --all、--max-pages；
- JSON 新增 status、summary、pagination 和逐项 stage；
- 查询字符串敏感 URL 的展示值改为安全形式。

禁止为了目录美观一次性移动所有实现。旧模块在过渡期保留薄兼容 façade，等调用点和测试全部迁移后再决定是否删除。

### 4.2 模块边界

计划采用以下依赖方向：

~~~mermaid
flowchart LR
    CLI["cli.py：入口与异常边界"] --> CMD["commands/*：参数注册与展示"]
    CMD --> RESULT["command_result.py：结构化命令结果"]
    CMD --> PAGE["pagination.py：有界分页"]
    CMD --> URL["url_ingest.py：URL 分流服务"]
    CMD --> UPLOAD["upload_service.py：上传状态机"]
    URL --> REMOTE["remote_http.py：无凭证公网 HTTP"]
    URL --> UPLOAD
    UPLOAD --> COS["cos_http.py：COS 流式 PUT"]
    UPLOAD --> KBAPI["knowledge_api.py：IMA API"]
    CMD --> NOTEAPI["notes_api.py：IMA API"]
    RESULT --> OUTPUT["output.py：唯一渲染出口"]
~~~

依赖规则：

- API client 不创建 service；
- service 不打印、不读取 argparse.Namespace；
- command 不直接构造 COS 请求；
- output 不调用 API；
- remote_http 不导入 Credentials、ImaHttpClient 或 CosCredential；
- cos_http 只接受已经验证的上传目标和只读文件流；
- security 与 validation 提供无副作用纯函数；
- 测试可为 clock、DNS resolver、connection factory、temp directory 和 API client 注入替身。

### 4.3 命令接口

保留并扩展：

~~~text
ima kb add-url
  --kb-id KB_ID
  --url URL [--url URL ...]
  [--folder-id FOLDER_ID]
  [--on-conflict error|rename]
  [--download-timeout 300]
  [--upload-timeout 300]
  [--json]

ima kb add-file
  --kb-id KB_ID
  --file PATH [--file PATH ...]
  [--folder-id FOLDER_ID]
  [--content-type MIME]
  [--on-conflict error|rename]
  [--upload-timeout 300]
  [--json]
~~~

约束：

- add-url 仍限制 1 至 10 个 URL；
- add-file 限制 1 至 2000 个文件，与 check_repeated_names 上限一致；
- 多文件 add-file 不允许使用单个全局 --content-type；每个文件必须可由扩展名识别；
- 单文件时继续支持 --content-type；
- timeout 必须为 1 至 3600 秒的整数；
- --on-conflict 默认 error；
- rename 只适用于文件分支，网页 URL 不执行重名检查；
- 不提供 overwrite 或 replace。

分页命令扩展：

~~~text
ima note search ... [--all] [--max-pages 100]
ima note folders ... [--all] [--max-pages 100]
ima note list ... [--all] [--max-pages 100]
ima kb search-base ... [--all] [--max-pages 100]
ima kb browse ... [--all] [--max-pages 100]
ima kb search ... [--all] [--max-pages 100]
ima kb addable ... [--all] [--max-pages 100]
~~~

### 4.4 CommandResult 和退出语义

新增 CommandResult，至少包含：

- payload：JSON 业务字段；
- human_lines：人类模式 stdout 行；
- warnings：人类模式 stderr、JSON warnings；
- status：success、empty、partial、failed；
- exit_code；
- error：仅 partial/failed 可选的安全聚合错误。

状态规则：

| status | ok | 退出码 | 含义 |
| --- | --- | --- | --- |
| success | true | 0 | 请求完全完成且至少一个结果成功 |
| empty | true | 0 | 请求成功但结果为空 |
| partial | false | 9 | 已产生可用结果，但未完成全部请求 |
| failed | false | 9 | 批量逐项结果已产生，但没有任何项成功 |
| error | false | 2 至 8、70、130 | 在形成可用逐项结果前发生分类异常 |

新增 ExitCode.PARTIAL = 9。

退出码 9 只用于“结果本身可用，但整体目标没有完全实现”。配置、协议、IMA envelope、单项命令和无法形成逐项结果的错误继续使用批次 B 的退出码。

JSON 模式规则：

- stdout 只有一个 JSON 文档；
- stderr 为空；
- partial/failed 同时包含 results 和 error；
- status 为新增的稳定字段；
- 既有业务字段保持顶层位置；
- warnings 始终是字符串数组；
- error 继续使用批次 B 的安全结构。

partial 示例：

~~~json
{
  "schema_version": 1,
  "ok": false,
  "status": "partial",
  "command": "kb.add-url",
  "warnings": [],
  "knowledge_base_id": "kb_xxx",
  "summary": {
    "total": 2,
    "succeeded": 1,
    "failed": 1,
    "not_attempted": 0
  },
  "results": [
    {
      "input_index": 0,
      "route": "web",
      "url": "https://example.com/article",
      "status": "success",
      "stage": "complete",
      "ret_code": 0,
      "media_id": "media_xxx"
    },
    {
      "input_index": 1,
      "route": "unsupported",
      "url": "https://www.youtube.com/watch",
      "status": "failed",
      "stage": "probe",
      "ret_code": null,
      "media_id": "",
      "error": {
        "code": "unsupported_url_type",
        "retryable": false
      }
    }
  ],
  "error": {
    "code": "partial_failure",
    "message": "1 of 2 items failed.",
    "exit_code": 9,
    "retryable": false
  }
}
~~~

示例中的 URL 不包含 query、fragment 或 userinfo。

### 4.5 用户 URL 的安全边界

探测和下载前必须满足：

- scheme 只能是 http 或 https；
- host 必须存在且是合法 DNS 名称；
- 禁止 userinfo；
- 禁止控制字符；
- http 只允许默认端口 80，https 只允许默认端口 443；
- 禁止 localhost 和以 .localhost 结尾的名称；
- 禁止 IP literal；
- DNS 解析出的每一个 IPv4/IPv6 地址都必须是全局可路由地址；
- 任一地址为 private、loopback、link-local、multicast、reserved、unspecified 时整次目标校验失败；
- 每一个重定向目标都重新执行完整校验；
- 最多跟随 5 次重定向；
- 禁止从 HTTP(S) 跳到其他协议；
- 禁用环境代理，避免校验目标与实际连接目标分离；
- 连接使用已校验并固定的 IP，HTTP Host 与 HTTPS SNI 仍使用原始域名；
- 不发送 Cookie、Authorization、IMA header、COS header 或用户自定义 header；
- 请求头只允许固定 User-Agent、Accept、Accept-Encoding、Range 和必要的 Host；
- 错误和结果中的 URL 只显示 scheme、host、port 和 path，剥离 query 与 fragment。

DNS resolver 和连接工厂必须可注入，以便测试无需真实 DNS 或网络。

### 4.6 URL 探测策略

每个 URL 的探测顺序：

1. 语法和明显不支持模式预检；
2. 对规范化 URL 发起 HEAD；
3. 跟随并校验重定向；
4. 若 HEAD 返回 405、501，或缺少足够的 Content-Type/Content-Disposition，则发起 GET；
5. GET 使用 Accept-Encoding: identity；如服务器支持，附带 Range: bytes=0-0；
6. GET 只读取响应头，不为探测保存正文；
7. 记录最终安全 URL、Content-Type、Content-Length、Content-Disposition；
8. 使用固定决策表分类。

分类优先级：

1. file URL、Bilibili 视频和 YouTube 视频立即 unsupported；
2. 明确认识的文件 MIME 进入 file；
3. text/html 或 application/xhtml+xml 根据 host/path 区分 wechat、web、unsupported video；
4. application/octet-stream 仅在 Content-Disposition 或最终 path 给出受支持扩展名时进入 file；
5. 缺失 MIME 时，仅允许已知文件 URL 模式或受支持扩展名进入 file；
6. 其他 MIME 进入 unsupported，不猜成网页。

已知文件 URL 模式至少覆盖：

- arxiv.org/pdf/；
- 受支持文件扩展名；
- GitHub raw 内容域名和 raw 路径；
- 重定向后最终路径的受支持扩展名。

冲突裁决：

- 明确文件 MIME 优先于路径扩展名；
- 明确 HTML MIME 优先于伪装成文件的 path；
- application/octet-stream 需要文件名或 path 佐证；
- Content-Disposition 只用于文件名和 octet-stream 佐证，不覆盖明确 HTML；
- MIME 与扩展名不一致时按 MIME 选择 media_type，并产生安全 warning；
- 不读取正文做 magic sniffing。

### 4.7 文件名推断和清洗

推断优先级与 1.1.7 一致：

1. Content-Disposition 的 filename*；
2. Content-Disposition 的 filename；
3. 最终 URL path 的最后一段；
4. download 加上 Content-Type 对应扩展名。

清洗规则：

- 只取 basename，不接受目录；
- 将正斜杠、反斜杠和控制字符替换为下划线；
- 去除 NUL、前后空白、Windows 尾随点和空格；
- 拒绝空名称、单点和双点；
- 规避 CON、PRN、AUX、NUL、COM1 至 COM9、LPT1 至 LPT9；
- 扩展名由已判定 media_type 校验，不允许任意脚本扩展名；
- 操作系统临时文件名限制在 240 个 UTF-8 字节内，保留扩展名；
- API 最终文件名限制在 1024 个 Unicode 字符内；
- 清洗导致名称变化时记录 warning；
- 不在错误中显示原始危险 filename。

### 4.8 有界下载

RemoteHttpClient.download_to 的不变量：

- 使用随机 TemporaryDirectory；
- 临时目录权限在平台允许时限制为当前用户；
- 先写 .part；
- 以 64 KiB 块读取；
- Content-Length 超过对应媒体类型上限时在写文件前拒绝；
- Content-Length 缺失时仍按实际累计字节执行硬上限；
- 总绝对上限为 200 MiB；
- 完成后校验实际大小与合法 Content-Length 一致；
- 关闭并 flush 文件后再改名为安全目标名；
- 返回 DownloadedFile 的 path 字段 repr=False；
- 返回 bytes_count、sha256、content_type、safe_name 和 final_host；
- 网络中断不保留半文件；
- service 退出 TemporaryDirectory 上下文前必须完成上传；
- 任何日志、JSON 和异常都不暴露临时绝对路径。

下载是安全读取，可在完全重建临时文件的前提下进行最多 2 次有限重试；不做断点续传。类型错误、大小错误、4xx、重定向安全错误不重试。

### 4.9 统一上传状态机

UploadService 的每个候选项遵循：

~~~mermaid
stateDiagram-v2
    [*] --> Preflight
    Preflight --> ConflictCheck
    ConflictCheck --> Renamed: repeated and policy=rename
    ConflictCheck --> Failed: repeated and policy=error
    Renamed --> ConflictRecheck
    ConflictRecheck --> Ready
    ConflictCheck --> Ready: not repeated
    Ready --> SnapshotCheck
    SnapshotCheck --> CreateMedia
    CreateMedia --> CredentialCheck
    CredentialCheck --> CosUpload
    CosUpload --> PostUploadCheck
    CosUpload --> Failed: COS failure
    PostUploadCheck --> Register
    PostUploadCheck --> Failed: file changed
    Register --> Complete
    Register --> Orphaned: add_knowledge failure
    Complete --> [*]
    Failed --> [*]
    Orphaned --> [*]
~~~

严格顺序：

1. 所有候选项本地预检；
2. 所有候选项一次性 check_repeated_names；
3. 处理冲突并对 rename 名称再次检查；
4. 每项 create_media；
5. 校验该项 COS 凭证；
6. 流式 PUT；
7. 复核文件；
8. add_knowledge。

任何前置批量检查失败时，不得调用 create_media。

### 4.10 文件快照和变更检测

UploadFileInfo 扩展为不可变快照，至少记录：

- resolved path，repr=False；
- st_dev；
- st_ino；
- st_size；
- st_mtime_ns；
- media_type；
- content_type；
- source_name；
- final_name；
- file_ext。

执行规则：

- 预检 stat 一次；
- create_media 前重新 stat；
- 打开文件后 fstat，并与快照比较；
- COS 发送使用同一个已打开文件描述符；
- 发送完成后再次 fstat；
- add_knowledge 前再次 stat path，确认路径仍指向相同文件；
- 任一 identity、size、mtime_ns 变化均抛出 file_changed_during_upload；
- 发生变化时，即使 COS 已成功也不得 add_knowledge；
- 结果标记 stage=post_upload_check 和 orphaned_media=true；
- 不尝试删除或覆盖远端对象。

### 4.11 重名和 rename 算法

error 策略：

- 默认；
- 发现任一服务端重名或批次内最终名称重复时，在任何 create_media 前终止该批次；
- 单文件命令返回 InputError；
- 多项命令形成逐项结果时，冲突项为 failed，未发生副作用的其他项为 not_attempted，整体退出 9。

rename 策略：

- 格式为 stem_YYYYMMDDHHmmss.ext；
- clock 通过依赖注入固定；
- 保留原扩展名；
- 同一秒内出现多个相同名称时追加 _2、_3；
- 名称长度超限时先截短 stem，再追加后缀；
- 生成后检查批次内唯一性；
- 对所有改名候选再次调用 check_repeated_names；
- 若仍重复，增加序号并最多重试 100 个候选名；
- 超出上限安全失败，不回退覆盖；
- 最终名称同时用于 create_media.file_name、file_info.file_name、add_knowledge.title 和结果输出；
- 本地文件本身不重命名。

### 4.12 COS 流式 PUT

cos_http.py 使用标准库 http.client 和默认 TLS 上下文。

不变量：

- 只连接 build_and_validate_cos_origin 返回的官方 HTTPS host；
- 忽略 custom_domain；
- 使用固定 Content-Length；
- 每次最多从文件流读取 64 KiB；
- 禁止 read() 无 size；
- 不把文件复制为 bytes；
- 签名 header 中 host、content-length 与实际请求完全一致；
- 签名 pathname 与发送 pathname 完全一致；
- 不自动跟随 3xx；
- 不自动重试；
- 2xx 才算成功；
- 错误正文最多读取 16 KiB，且不回显；
- timeout 默认 300 秒；
- 连接、发送和读取错误统一为 KnowledgeUploadError；
- Authorization、security token、secret ID、secret key 永不进入 repr、异常、JSON 或日志。

大文件验收不依赖真实 COS：

- 测试替身拒绝无界 read；
- 记录最大单次 read 不超过 64 KiB；
- 断言 Path.read_bytes 未被调用；
- 可选本地压力测试使用稀疏 200 MiB 文件，峰值额外内存应明显低于文件大小。

### 4.13 COS 凭证和对象 key

凭证检查：

- token、secret_id、secret_key、bucket_name、region、cos_key 非空；
- start_time、expired_time 是非 bool 整数；
- start_time < expired_time；
- 允许最多 300 秒本地时钟偏差；
- 凭证不得已经过期；
- 开始上传时至少剩余 30 秒有效期；
- 凭证剩余时间不足时在网络前失败；
- 任何错误不包含凭证字段值。

cos_key 规则：

- 作为相对对象 key 处理；
- 不得是 URL；
- 不得含 scheme、authority、query 或 fragment；
- 不得以斜杠或反斜杠开头；
- 不得含反斜杠、控制字符、空 segment、单点或双点 segment；
- 逐 segment 执行一次 URL 编码；
- slash 作为层级分隔符保留；
- 原始 key、规范 key、签名 path 和请求 path 的关系有固定测试向量；
- file_info.cos_key 使用验证后的规范 key。

### 4.14 批量执行与失败聚合

输入顺序是结果顺序。

add-url：

- 先探测全部 URL；
- web/wechat 项合并为一次 import_urls 调用；
- file 项下载后形成上传候选；
- unsupported 项保留逐项失败；
- 服务端 results map 按请求 URL 回填，不能依赖 JSON map 顺序；
- 缺少请求项或出现未知结果项视为 ApiProtocolError；
- 不把网页 URL 混入文件重名检查。

add-file：

- 先预检全部本地文件；
- 再一次性重名检查；
- 单个 --file 保持既有顶层结果字段；
- 多个 --file 增加 results 和 summary。

继续策略：

- 单项输入、文件类型或冲突错误不会阻止其他已经通过预检的 add-url 项；
- IMA 配置、认证、顶层协议错误会停止剩余项；
- COS 单项失败后不调用该项 add_knowledge，但可继续下一个已准备项；
- KeyboardInterrupt 立即停止，已完成项不回滚，退出 130；
- 未开始项标记 not_attempted；
- 任何 partial/failed 结果不得被包装成 exit 0。

每个结果项至少包含：

- input_index；
- source_kind：local_file、web_url、file_url；
- 安全 source 名称；
- route；
- status；
- stage；
- final_name；
- renamed；
- media_id；
- ret_code；
- orphaned_media；
- 安全 error。

### 4.15 分页策略

新增通用 PageRequest 和 PageCollection。

默认行为：

- 未传 --all 时只取一页；
- 现有 --cursor、--start 和 --limit 语义不变；
- limit 是每页大小，不改成总数上限。

--all 行为：

- 从用户给定 cursor/start 开始；
- max-pages 默认 100，允许 1 至 1000；
- is_end=true 时停止；
- cursor 重复时抛 ApiProtocolError；
- is_end=false 且 next_cursor 为空时抛 ApiProtocolError；
- offset 页返回空列表但 is_end=false 时抛 ApiProtocolError；
- offset 通过实际返回数量推进，且必须严格增加；
- 结果保持服务端页序和页内顺序；
- 达到 max-pages 但尚未结束时返回 status=partial、exit 9、truncated=true；
- JSON 保留原 next_cursor/is_end，并增加 pagination 对象；
- pagination 包含 all_requested、pages_fetched、max_pages、truncated、start 和 next。

不在本批次对业务条目按 ID 自动去重，因为服务端顺序和重复本身可能有语义；只检测游标无进展。

### 4.16 CLI 输出和展示

迁移后：

- command handler 不接收 as_json；
- command handler 不调用 print；
- service 不知道 stdout/stderr；
- output.py 是唯一 JSON dump 出口；
- 人类 warning 只写 stderr；
- 人类结果只写 stdout；
- JSON warning 合并到 warnings；
- parser 错误仍能根据 argv 中的 --json 进入统一 JSON 错误；
- help 仍为 argparse 人类文本；
- partial 人类模式先输出逐项结果，再在 stderr 输出安全汇总，返回 9。

人类展示：

- 已有名称时名称优先；
- ID 放在次级行，不在标题中堆叠；
- URL 不显示 query/fragment；
- 文件路径只显示 basename；
- 不打印内部 create_media、COS 签名等步骤；
- 失败时显示项、阶段和可操作建议。

### 4.17 类型策略

采用：

- dataclass：服务领域结果、上传快照、URL 探测结果、CommandResult；
- Enum：route、stage、status、conflict policy；
- TypedDict：为保持运行时 dict 兼容的 API client 返回值；
- Protocol：API client、resolver、connection factory、clock 等可注入依赖；
- Mapping：只用于通用输出边界。

不再使用：

- 已知模型上的 object/getattr；
- service 中的 dict[str, Any] 字符串键编排；
- 把异常状态编码为空字符串；
- bool(value) 解析协议布尔值。

knowledge_api 和 notes_api 原有 dataclass 的导入路径继续有效。新服务类型从 api.py 导出，但私密的 DownloadedFile path 和凭证类型不做可序列化导出。

### 4.18 名称解析的裁决

阶段 5 要求“评估按名称解析知识库、文件夹和笔记”。

本批次裁决为：

- 不增加隐式模糊匹配；
- 不为格式化额外发起隐藏 API 请求；
- 不在多个同名结果中自动选择；
- 人类输出仅在现有响应已经包含名称时优先显示名称；
- JSON 保留完整 ID；
- 若后续实现名称选择，应使用显式参数、精确匹配和歧义错误，并单独设计契约。

理由：

- 文件夹名称在不同层级可重复；
- 笔记标题不唯一；
- 自动搜索会改变写操作调用数量和失败面；
- 1.1.7 明确要求目标不确定时不要猜测。

### 4.19 音频时长

不新增生产依赖的前提下：

- WAV 使用标准库 wave 读取帧数和采样率，超过 2 小时在 create_media 前拒绝；
- 非法 WAV 作为输入错误处理；
- MP3、M4A、AAC 继续执行类型和 200 MiB 大小检查，不猜测时长；
- README 明确压缩音频时长仍由服务端最终校验；
- 若产品要求客户端完整覆盖所有音频格式，先提交依赖评估，再征得确认。

## 5. 详细实施步骤

### C0.1 建立 URL 导入契约裁决文档

新增 docs/URL_INGEST_CONTRACT_1_1_7.md。

内容：

- 来源优先级；
- URL 安全边界；
- 重定向上限；
- HEAD/GET 策略；
- MIME 决策表；
- 文件名推断；
- 大小限制；
- 安全展示；
- 逐项状态；
- 1.1.7 歧义和本项目裁决。

验收：

- 每个分类分支有输入条件、route 和失败码；
- 文档不含真实 URL token、Cookie 或用户数据；
- 代码常量能逐项对应文档。

### C0.2 建立上传契约裁决文档

新增 docs/UPLOAD_CONTRACT_1_1_7.md。

内容：

- Gate 顺序；
- 快照字段；
- 重名策略；
- rename 算法；
- COS target/key；
- 凭证时效；
- timeout；
- 阶段性失败；
- 孤立 media；
- 音频时长边界。

验收：

- 明确无 replace；
- 明确不重试 COS PUT/add_knowledge；
- 明确无删除 API 时只报告孤立状态。

### C0.3 冻结 CLI JSON Schema v1

新增 docs/CLI_JSON_SCHEMA_V1.md。

内容：

- 公共成功、空、partial、failed、error 示例；
- status 与 ok 的关系；
- 退出码；
- warnings；
- pagination；
- summary；
- 逐项结果；
- URL/路径清洗；
- 兼容字段承诺。

验收：

- 现有批次 B JSON fixture 仍合法；
- partial 有结果也有 error；
- stderr 规则明确。

### C0.4 建立批次 C fixtures

新增 tests/fixtures/url_ingest/README.md 和脱敏 fixture：

- html_page.json；
- wechat_page.json；
- pdf_by_mime.json；
- pdf_by_disposition.json；
- octet_stream_by_filename.json；
- redirect_to_file.json；
- unsupported_video.json；
- private_redirect.json；
- missing_content_type.json；
- import_urls_mixed_result.json。

fixture 只描述请求方法、状态、headers 和安全 URL，不保存真实正文或凭证。

### C0.5 固化现有 CLI 兼容快照

在实施重构前增加测试：

- 所有命令 help 中现有参数仍存在；
- 单页 JSON 关键字段；
- add-file 单文件参数；
- add-url 网页 URL API payload；
- ima-note 入口改写；
- parser JSON 错误；
- auth 缺凭证语义。

这些测试是 CLI 拆分的安全网，不能在同一个提交中先删后补。

### C1.1 扩展错误和结果状态

修改 errors.py：

- 增加 ExitCode.PARTIAL=9；
- 增加 RemoteFetchError，退出码 7；
- 为安全 details 增加 stage、item_index、completed、failed、not_attempted；
- details 仍采用白名单，不允许 url、path、headers、credential；
- 保留所有批次 B 类和退出码。

新增 command_result.py：

- CommandStatus；
- CommandResult；
- ItemStatus；
- BatchSummary；
- 安全聚合函数。

测试：

- 状态与退出码组合不合法时构造失败；
- partial 必须带非零退出码；
- success/empty 必须为 0；
- summary 计数一致；
- error 字段不接受敏感 details。

### C1.2 增加用户 URL 安全纯函数

修改 security.py 或新增 validation.py 中专用函数：

- parse_public_http_url；
- safe_display_url；
- validate_public_addresses；
- validate_redirect_target；
- sanitize_remote_filename。

测试覆盖：

- http/https；
- userinfo；
- 非默认端口；
- IP literal；
- localhost；
- IPv4/IPv6 私网；
- 混合公私 DNS 结果；
- 控制字符；
- query 清洗；
- Windows 保留名；
- path traversal filename。

### C1.3 实现无凭证 RemoteHttpClient

新增 remote_http.py。

职责：

- DNS 解析与固定连接；
- HEAD；
- 受限 GET 探测；
- 手动重定向；
- header 规范化；
- 下载到文件流；
- 长度和 chunk 上限；
- 安全错误转换。

接口建议：

~~~text
probe(url) -> RemoteProbe
download_to(probe, destination, max_bytes) -> RemoteDownload
~~~

RemoteProbe 只保存原始 URL repr=False，公开 safe_url、final_host、content_type、content_length、disposition 和 redirect_count。

测试完全使用 resolver/connection fake，不访问互联网。

### C1.4 实现 URL 分类器

新增 url_ingest.py 中 UrlClassifier。

输入：

- 安全语法结果；
- RemoteProbe；
- 支持的 MIME/扩展名表。

输出：

- UrlRoute.WEB；
- UrlRoute.WECHAT；
- UrlRoute.FILE；
- UrlRoute.UNSUPPORTED；
- media_type；
- content_type；
- 推断文件名；
- warnings。

分类器必须是纯函数，fixture 表驱动测试不创建临时文件或网络。

### C1.5 实现安全临时下载

在 url_ingest.py 中实现 RemoteDownloadSession：

- 管理 TemporaryDirectory 生命周期；
- 生成安全文件名；
- 写 .part；
- 调用 RemoteHttpClient.download_to；
- fsync/flush 后改名；
- 生成 UploadCandidate；
- 离开上下文自动清理。

测试：

- 成功时文件存在于上下文内；
- 离开上下文后目录不存在；
- 大小超限、短读、网络中断、写失败均无残留；
- 结果 repr 不含 path；
- sha256 正确；
- Content-Length 不可信时仍有硬上限。

### C1.6 收紧 import_urls 结果关联

修改 knowledge_api.py：

- 为 import_urls 返回值增加 TypedDict；
- ImportUrlResult.ret_code 保持严格 int；
- 按请求 URL 验证 results；
- 缺失请求项、未知额外项、错误 inner url 均为 ApiProtocolError；
- 返回结果顺序与输入顺序一致；
- 不在协议错误中回显 URL。

若真实 1.1.7 fixture 证明服务端允许省略 inner url，以契约文档裁决为准，不以空字符串猜测。

### C1.7 实现 UrlIngestService

新增 url_ingest.py 中 UrlIngestService。

依赖：

- KnowledgeBaseApiClient Protocol；
- RemoteHttpClient；
- UploadService；
- temp factory；
- clock。

职责：

- 最多 10 项；
- 探测和分类；
- 聚合 web/wechat；
- 下载 file；
- 调用 UploadService；
- 保持输入顺序；
- 合并服务端 ret_code 与本地阶段；
- 输出 UrlIngestResult；
- 计算 CommandStatus 和退出码。

服务不打印、不生成 argparse 错误文本、不序列化完整 URL。

### C1.8 URL 流程单元测试

新增：

- tests/test_remote_http.py；
- tests/test_url_ingest.py；
- tests/test_url_security.py，或扩展 test_security.py。

关键断言：

- 从未构造 IMA/COS header；
- 每跳重新校验；
- DNS 固定；
- 私网重定向在第二次请求前失败；
- 最多 5 跳；
- HEAD 回退；
- HTML、微信、文件、unsupported 分流；
- 文件 URL 进入 UploadService；
- 网页 URL 只进入 import_urls；
- 混合结果顺序稳定；
- URL query token 不出现在 stdout、stderr、repr 和异常。

### C2.1 重构文件预检模型

修改 knowledge_upload.py，将它收敛为：

- 兼容导出；
- 文件类型表；
- inspect_upload_file；
- COS 签名纯函数。

上传状态机移到 upload_service.py，网络 PUT 移到 cos_http.py。

UploadFileInfo 增加快照字段和 final_name，path repr=False。

新增预检：

- 空文件；
- 名称长度；
- 安全 basename；
- WAV 时长；
- stat 错误分类；
- 多文件 content-type 规则。

### C2.2 实现 COS target 和凭证校验

修改 security.py，并在 cos_http.py 增加 CosUploadTarget：

- validate_cos_credential；
- normalize_cos_key；
- build target；
- 统一 encoded pathname；
- clock skew；
- 最小剩余有效期。

测试使用固定 clock 和固定签名向量。

### C2.3 实现流式 CosUploader

新增 cos_http.py。

接口建议：

~~~text
upload(file_handle, snapshot, credential, timeout) -> CosUploadResult
~~~

CosUploadResult 仅包含：

- bytes_sent；
- status_code；
- 可选安全 ETag；
- elapsed_ms。

不得包含 Authorization、token、secret、完整 URL 或文件 path。

连接层通过 Protocol 注入，以验证：

- 固定 Content-Length；
- 64 KiB；
- 无 read_bytes；
- 3xx/4xx/5xx；
- 短读；
- timeout；
- response body 中断；
- connection close。

### C2.4 实现 UploadService

新增 upload_service.py。

主要方法：

~~~text
prepare_local_files(...)
upload_candidates(...)
upload_one(...)
~~~

服务返回 UploadBatchResult 和 UploadItemResult，不返回裸 dict。

每个外部调用前后写入内存中的 stage；异常转换为逐项安全错误。stage 不写磁盘日志。

### C2.5 实现批量重名和冲突策略

UploadService：

- 一次发送全部 params；
- 验证返回名称集合与请求一致；
- 检测输入内重名；
- error 策略无副作用停止；
- rename 使用注入 clock；
- 重新 check；
- 最多 100 次候选；
- 最终名称全链路一致。

修改 knowledge_api.check_repeated_names：

- 返回顺序不可信，service 按 name 关联；
- 缺失、重复或未知 name 为 ApiProtocolError；
- 不通过 zip 静默配对。

### C2.6 实现文件变更保护

UploadService：

- create_media 前 verify_snapshot；
- 打开后 verify_fstat；
- 上传后 verify_fstat；
- 注册前 verify_path_identity；
- 变更后标记 orphaned_media；
- 禁止 add_knowledge。

测试在 fake uploader 回调中修改、截断、替换文件，分别验证每个分支。

### C2.7 实现阶段性失败和孤立 media 结果

结果规则：

- create_media 失败：media_id 为空、orphaned=false；
- COS 失败：media_id 可返回、orphaned=true；
- post-check 失败：orphaned=true；
- add_knowledge 失败：orphaned=true、stage=register；
- complete：orphaned=false；
- 不输出 cos_key 和凭证；
- 人类建议说明可重试整个命令可能创建新 media，不承诺自动清理。

### C2.8 上传测试矩阵

新增：

- tests/test_cos_http.py；
- tests/test_upload_service.py。

扩展：

- tests/test_knowledge_upload.py；
- tests/test_knowledge_api.py；
- tests/test_security.py。

必须覆盖每个 Gate 的成功和失败，以及调用顺序断言。

### C3.1 让 output.py 直接渲染 CommandResult

修改 output.py：

- render_command_result；
- render_json_result；
- render_human_result；
- partial JSON；
- warning channel；
- schema reserved fields；
- status；
- summary；
- error。

保留 emit_json_success、emit_json_error、emit_human_error 作为兼容函数，内部委托新实现。

### C3.2 移除 stdout 捕获式编排

修改 cli.py：

- 删除 _run_handler 的 stdout/stderr 捕获和 json.loads；
- handler 直接返回 CommandResult；
- 顶层只执行一次 render；
- ImaCliError 仍由统一异常边界处理；
- KeyboardInterrupt 仍为 130；
- 未分类异常继续清洗为 70；
- JSON 模式在解析前从 argv 识别。

验收：

- command 内部不再接收 as_json；
- JSON 输出不依赖 handler 自己 print；
- 测试可直接断言 CommandResult。

### C3.3 抽取共享 validation

新增 validation.py：

- require_non_empty_id；
- validate_limit；
- validate_max_pages；
- validate_timeout；
- validate_cursor；
- validate_url_count；
- validate_file_count；
- parse_conflict_policy。

API client 继续调用同一纯函数或保留等价保护，不能只依赖 CLI。

### C3.4 抽取 pagination

新增 pagination.py：

- CursorPage；
- OffsetPage；
- PageCollection；
- collect_cursor_pages；
- collect_offset_pages；
- loop/no-progress 检测；
- max-pages partial。

新增 tests/test_pagination.py，使用纯 fake fetcher。

### C3.5 新增 commands 包

新增：

- src/ima_note_cli/commands/__init__.py；
- commands/auth.py；
- commands/notes.py；
- commands/knowledge.py。

每个模块分为：

- register(parent_parser)；
- execute(args, context)；
- payload builder；
- human formatter。

注册函数接收公开的 ArgumentParser，不把 argparse._SubParsersAction 暴露为核心接口。

### C3.6 增加 AppContext 和惰性依赖

cli.py 或 commands/__init__.py 定义 AppContext：

- credentials；
- notes client factory；
- knowledge client factory；
- source client factory；
- remote client factory；
- upload service factory；
- clock/temp factory。

只为当前命令创建所需依赖：

- auth 不创建 API client；
- note 不创建 Knowledge client；
-普通 kb 查询不创建 RemoteHttpClient/CosUploader；
- kb add-url 才创建 URL 与上传服务；
- kb add-file 才创建上传服务；
- kb read/export 继续创建批次 B 的 MediaContentService。

### C3.7 迁移 Notes 命令

将 notes_cli.py 的行为迁移到 commands/notes.py：

- search/get/folders/list/create/append；
- 内容准备 warning；
- JSON payload；
- 人类格式；
- 分页 --all。

notes_cli.py 暂时保留兼容 re-export 或薄 façade。

迁移不得改变：

- note_id/doc_id 字段；
- Markdown 图片过滤；
- UTF-8；
- 搜索参数；
- ima-note 行为。

### C3.8 迁移 Knowledge 查询与媒体命令

将 knowledge_cli.py 的查询、add-note、media-info、read、export 迁移到 commands/knowledge.py。

接入 pagination，并保留批次 B 的媒体安全边界。

path_node_to_dict 和 import_url_result_to_dict 改为明确类型参数，不再使用 getattr。

### C3.9 接入 add-url 和 add-file

commands/knowledge.py：

- add-url 调用 UrlIngestService；
- add-file 调用 UploadService；
- 生成兼容顶层字段；
- 多项结果和 partial；
- timeout 与 conflict 参数；
- warning；
- 安全人类输出。

CLI 不再直接执行 check_repeated_names、create_media、upload_to_cos 或 add_file。

### C3.10 保留旧模块兼容入口

knowledge_cli.py 与 notes_cli.py：

- 保留历史导入函数需要的最小 wrapper；
- validate_urls 转发到新 validation/classifier 的纯语法预检；
- 不保留两份业务实现；
- 标注内部弃用但不在本批次删除。

若仓库内外没有公共承诺，也至少保留到批次 D 后再评估。

### C3.11 更新公共 Python API

修改 api.py：

- 导出 UploadService、UrlIngestService；
- 导出安全的结果类型；
- 导出 ConflictPolicy；
- 保留现有导出；
- 不导出内部连接类、临时路径或凭证序列化辅助。

修改 knowledge_api.py 的返回类型注解，保持运行时 dict 兼容的位置使用 TypedDict。

### C3.12 CLI 与 JSON 回归测试

新增 tests/test_cli_batch_c.py。

至少覆盖：

- add-url 网页成功；
- add-url 文件成功；
- 混合 partial 退出 9；
- 全部逐项失败；
- JSON stderr 为空；
- 人类 warning 在 stderr；
- URL token 不泄露；
- add-file 单文件兼容字段；
- add-file 多文件 summary；
- conflict error/rename；
- timeout 参数；
- --all；
- max-pages partial；
- parser 错误；
- ima-note；
- 批次 B media 命令回归。

### C4.1 更新活动文档

修改 README.md：

- add-url 自动分流；
- add-file 多文件；
- conflict；
- timeout；
- partial 退出码 9；
- --all；
- JSON status；
- URL 与临时文件安全；
- 流式上传；
- 音频限制；
- 孤立 media 提示。

修改 skills/ima-note-cli/SKILL.md：

- 只同步当前 CLI 的真实命令和安全行为；
- 不在本批次解决多个 skill 版本的 canonical 问题；
- 不复制上游 CJS 命令作为 Python CLI 的运行依赖。

### C4.2 更新现有契约和总计划

修改：

- docs/KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md，补充与用户 URL 客户端的边界；
- docs/API_CONTRACT_1_1_7.md，补充 import_urls 结果关联和上传裁决引用；
- OPTIMIZATION_PLAN.md，链接本计划并在实施完成后勾选对应项。

不修改 ima-skills-1.1.7 (1) 原始资料。

### C4.3 总体验证与对抗性检查

最后执行：

- 全量单测；
- compileall；
- 文档链接和敏感词搜索；
- 所有网络入口盘点；
- read_bytes 和无界 read 搜索；
- 所有 print/json.dumps 入口盘点；
- git diff --check；
- 工作区状态确认。

## 6. 涉及文件

### 6.1 新增文件

| 文件 | 用途 |
| --- | --- |
| BATCH_C_IMPLEMENTATION_PLAN.md | 本计划 |
| docs/URL_INGEST_CONTRACT_1_1_7.md | 用户 URL 分流与安全裁决 |
| docs/UPLOAD_CONTRACT_1_1_7.md | 上传 Gate、冲突、COS 与失败裁决 |
| docs/CLI_JSON_SCHEMA_V1.md | JSON/状态/退出码契约 |
| src/ima_note_cli/command_result.py | 命令和批量结果模型 |
| src/ima_note_cli/validation.py | 共享输入校验 |
| src/ima_note_cli/pagination.py | 有界分页收集 |
| src/ima_note_cli/remote_http.py | 无凭证公网 URL 探测与下载 |
| src/ima_note_cli/url_ingest.py | URL 分类、下载会话和分流服务 |
| src/ima_note_cli/cos_http.py | COS target、签名请求和流式 PUT |
| src/ima_note_cli/upload_service.py | 上传状态机与批量编排 |
| src/ima_note_cli/commands/__init__.py | 命令包公共接口 |
| src/ima_note_cli/commands/auth.py | auth 注册和展示 |
| src/ima_note_cli/commands/notes.py | Notes 命令适配 |
| src/ima_note_cli/commands/knowledge.py | Knowledge 命令适配 |
| tests/test_command_result.py | 状态、汇总和退出码 |
| tests/test_pagination.py | cursor/offset/max-pages |
| tests/test_remote_http.py | 公网 HTTP 与重定向安全 |
| tests/test_url_ingest.py | URL 分类和混合流程 |
| tests/test_cos_http.py | 流式 COS PUT |
| tests/test_upload_service.py | 上传 Gate 和阶段失败 |
| tests/test_cli_batch_c.py | CLI/JSON/partial 回归 |
| tests/fixtures/url_ingest/README.md | fixture 来源和脱敏说明 |
| tests/fixtures/url_ingest/*.json | URL 探测与导入样例 |

最终实施时可以把紧密耦合的小模型放入对应 service 模块，避免为每个 dataclass 建文件；但不能重新把网络、状态机和 CLI 合回一个大型模块。

### 6.2 修改文件

| 文件 | 修改 |
| --- | --- |
| OPTIMIZATION_PLAN.md | 链接本计划，完成后更新阶段状态 |
| README.md | URL、上传、分页、JSON 和退出码 |
| docs/API_CONTRACT_1_1_7.md | import_urls、上传和 partial 裁决 |
| docs/KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md | 区分媒体 URL 与用户 URL |
| src/ima_note_cli/errors.py | partial 和 RemoteFetchError |
| src/ima_note_cli/output.py | 直接渲染 CommandResult |
| src/ima_note_cli/security.py | 公网 URL、COS key 和凭证时效 |
| src/ima_note_cli/knowledge_api.py | 严格结果关联和 TypedDict |
| src/ima_note_cli/knowledge_upload.py | 预检/签名兼容 façade |
| src/ima_note_cli/knowledge_cli.py | 迁移后薄兼容层 |
| src/ima_note_cli/notes_cli.py | 迁移后薄兼容层 |
| src/ima_note_cli/cli.py | AppContext、直接结果和命令注册 |
| src/ima_note_cli/api.py | 新服务和安全结果导出 |
| tests/test_cli.py | 既有命令兼容 |
| tests/test_cli_batch_b.py | 批次 B 输出回归 |
| tests/test_output.py | status/partial |
| tests/test_errors.py | 退出码 9 与安全 details |
| tests/test_security.py | 公网 URL、COS key、凭证时间 |
| tests/test_knowledge_api.py | URL map 和重名 map 关联 |
| tests/test_knowledge_upload.py | 新预检与兼容函数 |
| skills/ima-note-cli/SKILL.md | 活动 CLI 行为最小同步 |

### 6.3 预计无需修改

- pyproject.toml；
- uv.lock；
- src/ima_note_cli/http.py；
- src/ima_note_cli/config.py；
- src/ima_note_cli/protocol.py；
- src/ima_note_cli/source_http.py；
- src/ima_note_cli/media_service.py；
- src/ima_note_cli/notes_content.py；
- ima-skills-1.1.7 (1) 原始目录；
- skills/ima-skills-1.1.2；
- skills/ima-note；
- CI 和发布元数据。

若实施中需要修改 source_http.py，只允许抽取无状态 MIME/长度辅助，不能放宽其 IMA/COS allowlist 或临时 header 重定向规则。

## 7. 验收矩阵

### 7.1 URL 语法和 SSRF

- [x] 只接受 http/https；
- [x] file URL 在网络前拒绝；
- [x] userinfo 在网络前拒绝；
- [x] 非默认端口在网络前拒绝；
- [x] IP literal、localhost、私网、回环、链路本地和保留地址在网络前拒绝；
- [x] DNS 混合返回中只要有一个非公网地址即拒绝；
- [x] 每个 redirect 重新校验；
- [x] 连接固定到已经校验的 IP，Host/SNI 保留域名；
- [x] 环境代理不改变目标；
- [x] 最多 5 次 redirect；
- [x] URL query/fragment 不出现在错误、repr、JSON 和人类输出；
- [x] 请求不包含 IMA/COS 凭证和 Cookie。

### 7.2 URL 分类

- [x] HTML 普通页面进入 import_urls；
- [x] 微信页面进入 import_urls；
- [x] Bilibili/YouTube 为 unsupported；
- [x] 明确文件 MIME 进入文件流程；
- [x] Content-Disposition filename 和 filename* 可推断文件名；
- [x] octet-stream 只有在受支持文件名/path 佐证时进入文件流程；
- [x] HTML 可覆盖伪 .pdf path；
- [x] arxiv 与 GitHub raw 有 fixture；
- [x] 未知 MIME 安全拒绝；
- [x] MIME/扩展名冲突产生 warning；
- [x] 不读取正文做类型猜测。

### 7.3 下载

- [x] 64 KiB 分块；
- [x] Content-Length 预检；
- [x] 实际读取硬上限；
- [x] 绝对上限 200 MiB；
- [x] 类型特定上限沿用上传表；
- [x] 长度不一致失败；
- [x] sha256 正确；
- [x] .part 不残留；
- [x] TemporaryDirectory 在所有分支清理；
- [x] temp path 不序列化；
- [x] 安全读取重试最多 2 次且每次重建文件；
- [x] 4xx、类型、大小和安全错误不重试。

### 7.4 文件预检

- [x] 空文件拒绝；
- [x] 不支持扩展名拒绝；
- [x] 视频拒绝；
- [x] 类型大小上限正确；
- [x] 文件名最长 1024 字符；
- [x] 危险 basename 拒绝或清洗；
- [x] 单文件 content-type 兼容；
- [x] 多文件带全局 content-type 在网络前拒绝；
- [x] WAV 超过 2 小时拒绝；
- [x] 非 WAV 压缩音频不伪造时长结果。

### 7.5 重名和冲突

- [x] check_repeated_names 始终早于 create_media；
- [x] 批量只做一次初始检查；
- [x] error 为默认；
- [x] error 不覆盖、不改名；
- [x] rename 格式正确；
- [x] 同秒同名有稳定序号；
- [x] rename 后再次服务端检查；
- [x] 最多 100 次候选保护；
- [x] 最终名称在 create_media、file_info、title 中完全一致；
- [x] 本地文件不被重命名；
- [x] 返回 map 缺失/额外项为协议错误。

### 7.6 COS 凭证和 key

- [x] secret repr 隐藏；
- [x] 过期、未生效、顺序错误和剩余时间不足在网络前失败；
- [x] bucket/region 注入在网络前失败；
- [x] custom_domain 被忽略；
- [x] cos_key URL、穿越、反斜杠、控制字符和空 segment 拒绝；
- [x] 签名 path 与请求 path 同一值；
- [x] 只访问官方 myqcloud.com HTTPS host；
- [x] 凭证值不进入错误和 JSON。

### 7.7 流式上传

- [x] 不调用 Path.read_bytes；
- [x] 不执行无界 read；
- [x] 最大 read 为 64 KiB；
- [x] Content-Length 等于快照大小；
- [x] 默认 timeout 300 秒；
- [x] 允许 1 至 3600 秒配置；
- [x] 3xx 不跟随；
- [x] 非 2xx 失败；
- [x] 错误正文读取有 16 KiB 上限；
- [x] COS PUT 不自动重试；
- [x] add_knowledge 不自动重试；
- [x] 200 MiB 压力验证不会额外占用同等内存。

### 7.8 文件变化和 Gate

- [x] create_media 前变化会停止且无远端副作用；
- [x] 打开后 identity 不同会停止；
- [x] 上传中截断/增长会失败；
- [x] COS 失败后不调用 add_knowledge；
- [x] 上传后 mtime/size/identity 变化后不调用 add_knowledge；
- [x] add_knowledge 仅在所有 Gate 通过后调用；
- [x] 每个 Gate 有调用顺序测试。

### 7.9 阶段失败和孤立 media

- [x] create_media 失败不标记孤立；
- [x] COS 后失败标记 orphaned_media；
- [x] add_knowledge 失败保留安全 media_id；
- [x] 不承诺不存在服务端临时对象；
- [x] 不尝试不存在的删除 API；
- [x] 结果含 stage；
- [x] 结果不含 credential、cos_key、完整 URL 和 temp path。

### 7.10 批量和退出码

- [x] add-url 1 至 10；
- [x] add-file 1 至 2000；
- [x] 结果保持输入顺序；
- [x] all success 为 success/0；
- [x] 空查询为 empty/0；
- [x] 混合结果为 partial/9；
- [x] 全部逐项失败为 failed/9；
- [x] 无逐项结果的输入错误仍为 2；
- [x] JSON partial stdout 单文档、stderr 空；
- [x] 人类 partial 有逐项结果和 stderr 汇总；
- [x] KeyboardInterrupt 保留已完成项语义但退出 130。

### 7.11 CLI 重构

- [x] handler 不接收 as_json；
- [x] handler 不 print；
- [x] service 不依赖 argparse；
- [x] cli 不捕获 stdout 再 json.loads；
- [x] output.py 是唯一 JSON dump 出口；
- [x] argparse 私有类型不作为核心公共接口；
- [x] knowledge_cli/notes_cli 只保留兼容 façade；
- [x] 已知模型不再使用 object/getattr；
- [x] api.py 旧导出保持；
- [x] ima-note 兼容入口保持。

### 7.12 分页

- [x] 默认仍为单页；
- [x] --all 覆盖所有支持命令；
- [x] --max-pages 默认 100；
- [x] 范围 1 至 1000；
- [x] cursor 循环失败；
- [x] 空 next_cursor 且未结束失败；
- [x] offset 无进展失败；
- [x] 达到 max-pages 为 partial/9；
- [x] pagination JSON 字段一致；
- [x] 现有顶层 next_cursor/is_end 保留。

### 7.13 回归、文档和工作区

- [x] 当前 103 个基线测试继续通过；
- [x] 新增测试全部离线；
- [x] 无真实凭证和用户数据；
- [x] README、CLI help、活动 skill 和契约一致；
- [x] 不修改上游 ima-skills-1.1.7 (1)；
- [x] 不新增生产依赖；
- [x] pyproject.toml 和 uv.lock 无无关变化；
- [x] 不提前实施批次 D；
- [x] git diff --check 通过；
- [x] 用户原有工作区改动未被覆盖。

## 8. 验证命令

实施过程中按聚焦顺序执行：

~~~bash
uv run python -m unittest tests.test_command_result tests.test_output tests.test_errors -v
uv run python -m unittest tests.test_remote_http tests.test_url_ingest tests.test_security -v
uv run python -m unittest tests.test_cos_http tests.test_upload_service tests.test_knowledge_upload -v
uv run python -m unittest tests.test_pagination tests.test_knowledge_api tests.test_notes_api -v
uv run python -m unittest tests.test_cli tests.test_cli_batch_b tests.test_cli_batch_c -v
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
~~~

命令面 smoke：

~~~bash
uv run ima --help
uv run ima note list --help
uv run ima kb add-url --help
uv run ima kb add-file --help
uv run ima-note --help
~~~

静态检查：

~~~bash
rtk rg -n "read_bytes|read\(\)" src/ima_note_cli
rtk rg -n "urlopen|build_opener|HTTPConnection|HTTPSConnection|Request\(" src/ima_note_cli
rtk rg -n "Authorization|security-token|secret_id|secret_key|api_key|Cookie" src tests
rtk rg -n "print\(|json\.dumps|redirect_stdout|redirect_stderr|json\.loads" src/ima_note_cli
rtk rg -n "object|getattr\(" src/ima_note_cli/commands src/ima_note_cli/*service.py
rtk rg -n "file://|localhost|is_private|is_loopback|is_link_local" src tests
rtk rg -n "on-conflict|upload-timeout|download-timeout|--all|max-pages" src tests README.md skills/ima-note-cli
rtk git diff --check
rtk git status --short
~~~

解释：

- read_bytes 在媒体导出测试或无关安全代码中出现时需人工判断；上传生产路径不得出现；
- 凭证词汇允许出现在字段定义、header 构造、redaction 和虚构测试中，真实值不得出现；
- json.loads 可用于解析服务端响应或测试，不得继续用于反向解析 handler stdout；
- 每个网络入口必须能指向目标校验、大小上限、超时、重定向和重试策略。

## 9. 可选的受保护 smoke

自动验收不访问互联网、不使用真实账户、不写入真实知识库。

若需要人工 smoke，分两级：

### 9.1 无 IMA 写入的公网探测 smoke

在明确允许联网后，使用无敏感参数的公开测试 URL 验证：

- HTML；
- 302 到 HTML；
- PDF；
- Content-Disposition；
- 超限 Content-Length。

只运行 probe/classify，不调用 import_urls、create_media 或 COS。

### 9.2 专用测试账户写入 smoke

只有在用户明确授权、使用专用知识库并接受产生孤立 media 的可能性后执行：

~~~text
1. 上传小型 TXT。
2. 再次上传，验证默认 conflict error。
3. 使用 rename，验证最终名称。
4. 添加一个网页 URL。
5. 添加一个小型文件 URL。
6. 使用一个成功和一个服务端拒绝 URL 验证退出码 9。
~~~

smoke 输出必须先检查：

- 无凭证；
- 无完整签名 URL；
- 无本地绝对临时路径；
- 无 Authorization/Cookie。

## 10. 实施顺序与提交切片

### C-1：契约、结果模型和兼容快照

包含：

- 三份契约文档；
- fixture；
- CommandResult；
- ExitCode.PARTIAL；
- 现有 CLI 快照测试。

回滚边界：不改变生产工作流。

### C-2：公网 URL 安全客户端与分类

包含：

- security；
- remote_http；
- URL classifier；
- filename；
- 纯离线测试。

回滚边界：尚未接入 add-url。

### C-3：流式 COS 和 UploadService

包含：

- cos_http；
- 上传快照；
- 凭证/key；
- conflict；
- 状态机；
- Gate 测试。

回滚边界：旧 add-file 暂未切换。

### C-4：URL 下载与混合编排

包含：

- 临时下载；
- UrlIngestService；
- import_urls 关联；
- 文件 URL 接 UploadService；
- partial。

回滚边界：服务可独立测试，CLI 暂未切换。

### C-5：CLI 结果管线与命令拆分

包含：

- output；
- cli；
- commands；
- validation；
- AppContext；
- 移除 stdout 反解析。

回滚边界：所有旧命令兼容测试必须先绿。

### C-6：分页与写命令切换

包含：

- pagination；
- --all；
- add-url；
- add-file；
- timeout/conflict；
- CLI batch C 测试。

回滚边界：可以独立回退新增参数和 service 接线，不回退批次 B。

### C-7：文档与总体验证

包含：

- README；
- 活动 skill；
- 契约引用；
- 全量测试；
- compileall；
- 对抗性安全检查。

每个切片必须保持全量测试通过；不得把 URL 网络层、COS 重写和 CLI 拆分压成一个不可审阅提交。

## 11. 主要风险与应对

### 风险 1：HEAD 与 GET 的真实服务行为不一致

应对：

- HEAD 信息不足才 GET；
- 决策依赖最终 GET headers；
- 不下载探测正文；
- 用 fixture 覆盖 405、501、缺 MIME 和重定向。

### 风险 2：公网 URL 引入 SSRF

应对：

- 全地址校验；
- 每跳校验；
- DNS 固定连接；
- 禁用代理；
- 默认端口；
- 无凭证；
- 私网对抗测试。

### 风险 3：DNS rebinding 绕过预解析

应对：

- 校验后连接固定 IP；
- HTTPS 使用原域名 SNI 和证书验证；
- 不让连接层再次按域名解析；
- resolver/connection 行为有单元测试。

### 风险 4：过度严格导致企业内网 URL 不可用

应对：

- 明确 CLI 只自动下载公网 URL；
- 内网文件要求用户先安全下载再 add-file；
- 不提供跳过安全检查开关；
- 文档给出可操作替代方案。

### 风险 5：Content-Type 错误导致误分类

应对：

- 固定优先级；
- HTML 不因 .pdf path 下载；
- octet-stream 要求文件名佐证；
- 不做 magic sniffing；
- 冲突产生 warning。

### 风险 6：远程文件名造成路径穿越或 Windows 错误

应对：

- basename；
- 控制字符和分隔符清洗；
- 保留名保护；
- 长度限制；
- 随机临时目录；
- 原始危险名称不回显。

### 风险 7：流式 PUT 签名与实际 path/header 不一致

应对：

- CosUploadTarget 单一对象生成 origin、host、pathname；
- 同一 headers map 用于签名和请求；
- 固定向量；
- 编码一次；
- 禁止 redirect。

### 风险 8：上传期间文件变化

应对：

- stat/fstat；
- 同一文件描述符；
- 上传后复核；
- 不调用 add_knowledge；
- 报告孤立状态。

### 风险 9：rename 后仍发生竞态重名

应对：

- rename 后重新 API 检查；
- 服务端最终仍可能竞态，add_knowledge 错误按阶段报告；
- 不自动覆盖；
- clock 和序号确定性测试。

### 风险 10：add_knowledge 失败产生孤立 media

应对：

- 明确结果；
- 保留 media_id；
- 不泄露凭证；
- 不虚构删除能力；
- 文档说明重试可能产生新 media。

### 风险 11：CLI 重构破坏现有 JSON

应对：

- 重构前冻结快照；
- schema v1 只做加法；
- 单文件顶层字段保持；
- 兼容 façade；
- 旧测试与新测试并行。

### 风险 12：partial 退出码影响旧自动化

应对：

- 只有此前被错误视为成功的部分失败改为 9；
- 全成功仍为 0；
- README 和 schema 文档明确；
- JSON 仍保留逐项 ret_code/media_id；
- 提供 fixture 测试。

### 风险 13：批量继续执行扩大远程副作用

应对：

- 所有本地预检和重名检查先完成；
- 配置/协议类错误停止剩余项；
- 逐项阶段和 not_attempted 明确；
- 不并行上传；
- KeyboardInterrupt 立即停止。

### 风险 14：分页 --all 无限循环或拉取过多

应对：

- cursor 集合；
- offset 进度；
- 默认 100 页；
- 最大 1000；
- 达到上限 partial/9；
- 默认仍为一页。

### 风险 15：音频时长需要第三方依赖

应对：

- 本批次只用 wave 覆盖 WAV；
- 压缩格式不猜测；
- 需要依赖时先评估并确认；
- 不偷偷修改 pyproject/uv.lock。

### 风险 16：范围扩张到批次 D

应对：

- 只最小同步活动 CLI skill；
- 不整理多个 skill 目录；
- 不引入 CI/lint/release；
- 不改上游资料；
- 文件清单与验收中单独检查。

## 12. 完成定义

批次 C 只有在以下条件同时满足时才算完成：

1. 用户 URL 有独立、无凭证、逐跳校验的公网 HTTP 客户端。
2. 私网、localhost、IP literal、userinfo、非默认端口和危险重定向在网络前或下一跳前被拒绝。
3. HTML、微信、文件、Bilibili、YouTube 和 unknown 分类有固定契约与测试。
4. 文件名按 Content-Disposition、URL path、MIME 顺序推断并安全清洗。
5. 文件型 URL 使用有界临时下载，所有失败路径无残留。
6. 下载和上传均不一次性加载大文件。
7. UploadService 独立于 CLI，并实现完整 Gate 顺序。
8. 空文件、大小、文件名和 WAV 时长在 create_media 前检查。
9. check_repeated_names 始终早于 create_media，批量初始检查一次完成。
10. 默认 conflict error，不支持 replace。
11. rename 可重复验证，最终名称贯穿 create_media、file_info 和 title。
12. COS 凭证、官方 host、有效期和 key 在网络前严格校验。
13. COS PUT 为固定长度 64 KiB 流式发送，默认 timeout 300 秒，不自动重试或跟随重定向。
14. 上传前后文件身份、大小和修改时间得到复核。
15. COS 或复核失败后绝不调用 add_knowledge。
16. add_knowledge 失败明确报告孤立 media，且不泄露任何凭证。
17. add-url 网页和文件分支可以混合执行，结果保持输入顺序。
18. import_urls ret_code 非零会导致 partial/failed 非零退出。
19. JSON partial 是单个安全文档，stderr 为空，退出码为 9。
20. Command handler 返回 CommandResult，不再通过 stdout 反向解析 JSON。
21. 命令注册、服务、校验、分页和输出边界清晰，service 可脱离终端测试。
22. 所有可分页命令支持有上限的 --all，默认单页行为不变。
23. 现有命令、JSON 业务字段、api.py 导出和 ima-note 入口保持兼容。
24. 当前 103 个批次 B 基线测试继续通过，新测试全部通过。
25. 所有测试离线，无真实凭证、用户数据或真实知识库写入。
26. README、CLI help、活动 CLI skill 和三份新契约与实现一致。
27. 未新增生产依赖；pyproject.toml 和 uv.lock 无无关变化。
28. 未修改上游 ima-skills-1.1.7 (1) 原始资料。
29. 未提前实施批次 D 的 skill 归一、CI 和发布工作。
30. compileall、静态安全检查、git diff --check 和工作区检查通过。

完成批次 C 后，项目的核心 API、原文、URL 导入、文件上传和 CLI 结构优化即具备闭环；随后进入批次 D，处理 canonical skill、工程化门禁、打包和发布。
