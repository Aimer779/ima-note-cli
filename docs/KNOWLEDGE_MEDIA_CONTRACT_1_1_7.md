# Knowledge / Media API 1.1.7 契约裁决

## get_media_info

固定请求为 `POST /openapi/wiki/v1/get_media_info`，body 仅含非空 `media_id`。合法响应分支互斥：

- `media_type == 11`：必须含 `notebook_ext_info.notebook_id`，内部映射为 `note_id`，不得同时含 `url_info`；
- 非 11 且含 `url_info`：必须含非空 HTTPS `url`，`headers` 若存在必须为安全字符串映射；
- 非 11 且无 `url_info`：合法的 `unavailable` 元数据，不发第二个请求。

安全序列化只包含 media ID/type、source kind、note ID、安全 host 与 header 名称。完整 URL、query、header 值均为敏感信息，不进入 repr、JSON 或错误。

## 原文边界

初始 URL 只允许 `ima.qq.com` 或标签边界正确的 `*.myqcloud.com` HTTPS host，拒绝 userinfo、IP、localhost、非默认端口和控制字符。原文 GET 使用独立客户端，不携带 IMA Client ID/API Key；跨源重定向被拒绝。文本读取要求明确文本 MIME，最大 4 MiB并严格按声明 charset（缺省 UTF-8）解码。导出按 64 KiB 流式处理，最大 200 MiB，使用同目录临时文件、SHA-256 和原子替换，默认拒绝覆盖。

## Knowledge 严格字段与数量

集合字段必须为数组/对象且不能用 null 伪装空集合；关键 kb/folder/media ID 必须是非空字符串；布尔只接受 JSON boolean，整数拒绝 boolean。`search_knowledge_base` limit 为 1–20，browse/addable 为 1–50，get IDs 为 1–20 且唯一，import URLs 为 1–10，repeated names 为 1–2000。`create_media` 必须返回 media ID 和完整 COS credential；`add_knowledge` 必须返回 media ID；`import_urls` 的成功项必须返回 media ID。

## 待受保护只读 smoke 验证

1. 实际媒体 URL host 是否仅为 IMA/COS；
2. URL 响应是否稳定提供 Content-Type/Length；
3. 笔记分支是否可能同时出现 `url_info`；
4. 不可访问媒体是否可能返回空对象 `url_info`；
5. 临时 headers 除 Authorization 外是否还有必需字段；
6. URL 是否发生跨 host 重定向。

任何新 host 都必须先确认官方所有权并补 fixture/allowlist；不得把真实响应、ID、签名或正文写入测试。
