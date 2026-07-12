# 阶段 6 详细实施计划：统一 skills 与文档

> 编制日期：2026-07-12  
> 对应总计划：OPTIMIZATION_PLAN.md 的阶段 6，以及批次 D 中的 skills 与文档部分  
> 实施基线：批次 A、B、C 已实施，当前测试为 127/127 通过  
> 计划状态：待实施  
> 生产依赖策略：不新增生产依赖；校验器、生成器和测试仅使用 Python 标准库  
> 技能规范：按 skill-creator 要求，canonical SKILL.md 仅保留 name/description frontmatter、正文控制在 500 行内，并生成匹配的 agents/openai.yaml

## 1. 阶段目标

阶段 6 的目标不是把所有上游文件简单复制到 skills 目录，而是建立一套不会再次漂移的事实源和分发边界：

1. 仓库只保留一个可被 agent 发现并使用的 active skill。
2. 上游 1.1.7 作为可审计的只读来源归档，不与项目 skill 混在同一发现目录。
3. 旧版 1.1.2 和独立 ima-note skill 的有效信息完成迁移后退出 active 集合。
4. API 契约、CLI help、README 和 canonical skill 有清晰的派生方向。
5. CLI wheel 与 skill 的分发方式明确，不再把“仓库里存在”描述成“安装 CLI 后自动可用”。
6. 上游来源、发布者、版本、发布时间、MIT-0 许可证证据和 SHA-256 校验可复核。
7. 元数据、版本、命令覆盖和 Markdown 链接通过仓库内的离线检查自动验证。

完成后的结构目标：

~~~text
skills/
├── manifest.json
└── ima-note-cli/
    ├── SKILL.md
    └── agents/
        └── openai.yaml

docs/
├── IMA_OPENAPI_CONTRACT_1_1_7.md
├── CLI_REFERENCE.md
├── SKILL_DISTRIBUTION_POLICY.md
└── SKILL_MIGRATION_1_1_7.md

third_party/
└── ima-skills/
    └── 1.1.7/
        ├── UPSTREAM.json
        ├── SHA256SUMS
        ├── LICENSE.MIT-0
        └── original/
            └── 上游原始文件
~~~

其中：

- skills/ima-note-cli 是唯一 active skill；
- third_party 下的 SKILL.md 只是原样来源快照，不位于 active skills 根目录；
- docs/IMA_OPENAPI_CONTRACT_1_1_7.md 是唯一规范 API 契约文档；
- docs/CLI_REFERENCE.md 从 argparse parser 生成，不手工维护；
- README 是用户入口文档；
- canonical skill 只教 agent 安装和使用 Python CLI，不再复制原始 API schema；
- wheel 只包含 Python CLI，不包含或自动安装 skills。

## 2. 当前基线与仓库发现

### 2.1 测试和实现基线

当前执行：

~~~bash
uv run python -m unittest discover -s tests -v
~~~

结果为 127/127 通过。

当前 CLI 已包含：

- Notes 1.1.7 endpoint 与 note_id；
- Knowledge 查询、导入和上传；
- media-info、read、export；
- URL 类型探测与文件型 URL 下载；
- 流式 COS 上传；
- --on-conflict error|rename；
- --all 与 --max-pages；
- JSON status、summary、stage；
- 部分成功退出码 9；
- ima-note 兼容入口和 --doc-id 兼容别名。

因此阶段 6 必须以当前 parser、测试和实现为准，不能继续照抄批次 A/B 之前的命令或字段。

### 2.2 当前 skill 数量与角色

skills 目录当前有三个一级目录：

| 路径 | 当前角色 | 问题 |
| --- | --- | --- |
| skills/ima-note-cli | Python CLI 使用说明 | 最接近 canonical，但缺 agents/openai.yaml 和独立版本登记 |
| skills/ima-note | Notes 原始 API 工作流 | 没有 YAML frontmatter；与 CLI skill 重叠；引用 raw API |
| skills/ima-skills-1.1.2 | 旧版统一上游 skill | 包含旧 endpoint、docid/doc_id 和 Node/CJS 流程 |

README 却写“自带两个相关 skill”，与目录实际数量不一致。

### 2.3 canonical 候选现状

skills/ima-note-cli/SKILL.md 当前：

- 有合法的 name 和 description frontmatter；
- folder 名与 name 都是 ima-note-cli；
- 194 行，低于 skill-creator 建议的 500 行；
- 已覆盖 ima、ima-note、Notes、Knowledge、原文和批次 C 核心行为；
- 仍有部分描述偏向旧状态；
- 没有 agents/openai.yaml；
- 没有项目级 skill version；
- 没有与 CLI parser 自动比对的机制；
- 没有明确说明 wheel 不会安装该 skill。

它是最适合成为唯一 canonical skill 的现有资产。

### 2.4 ima-note skill 现状

skills/ima-note/SKILL.md：

- 第一行直接是 Markdown 标题，没有 YAML frontmatter；
- 不能满足 canonical skill 的 name/description 发现规范；
- 主要指导 agent 直接调用 ima_api，而不是调用本项目的 ima CLI；
- 与 skills/ima-note-cli 的 Notes 命令和安全说明重复；
- references/api.md 与上游 1.1.7 notes/references/api.md 的 SHA-256 完全相同；
- 保留它会让“使用 CLI”与“直接拼 OpenAPI 请求”成为两个并列入口。

它的有效安全意图需要迁移，但不应继续作为 active skill。

### 2.5 旧版 1.1.2 现状

skills/ima-skills-1.1.2 包含：

- search_note_book；
- list_note_folder_by_cursor；
- list_note_by_folder_id；
- docid/doc_id 旧字段；
- preflight-check.cjs；
- cos-upload.cjs；
- 旧 API references；
- _meta.json 中的 1.1.2 版本。

这些内容已经被当前 1.1.7 Python 实现替代。继续保留在 skills 根目录会被误认为可用或 canonical。

### 2.6 上游 1.1.7 下载目录现状

项目根目录存在未跟踪目录：

~~~text
ima-skills-1.1.7 (1)/
~~~

已确认信息：

- _meta.json 的 slug 为 ima-skills；
- _meta.json 版本为 1.1.7；
- skill-card.md 记录发布者 iampennyli；
- skill-card.md 记录来源页 https://clawhub.ai/iampennyli/ima-skills；
- skill-card.md 标注 MIT-0；
- meta.json 声明 Node.js 18；
- 根 SKILL.md 包含额外 homepage、metadata 和安全字段；
- 包含 ima_api.cjs、preflight-check.cjs、cos-upload.cjs；
- 包含 Notes 和 Knowledge 原始 references。

问题：

- 目录名含下载器生成的 (1)；
- 未被 Git 跟踪；
- 没有仓库级来源登记；
- 没有完整 SHA-256 manifest；
- 没有独立的 MIT-0 许可证文本文件；
- 与 active skills、项目代码和文档混在根目录；
- 上游根 SKILL.md 的 frontmatter 不符合本项目 canonical skill 的“只保留 name/description”规范；
- 上游 CJS 行为不能直接代表当前 Python CLI 的安全边界。

### 2.7 API 契约来源现状

当前至少存在：

- docs/API_CONTRACT_1_1_7.md；
- docs/KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md；
- skills/ima-note/references/api.md；
- skills/ima-skills-1.1.2 下的 references；
- ima-skills-1.1.7 (1) 下的 references；
- README 中的命令和行为说明；
- canonical CLI skill 中的命令和行为说明；
- tests/fixtures 下的 executable examples。

其中 docs/API_CONTRACT_1_1_7.md 仍将含 (1) 的下载路径写成依据，且两份 docs 在批次 C 后以追加小节方式扩展，没有统一目录或索引。

### 2.8 wheel 分发现状

pyproject.toml 当前只配置：

~~~toml
[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where = ["src"]
~~~

因此：

- wheel 只发现 src/ima_note_cli；
- 根目录 skills 不在 wheel；
- uv tool install 安装 CLI，不会把 skill 安装到 agent 的 skill discovery 目录；
- README 使用“项目自带”容易让用户误以为 CLI 安装后 skill 也自动可用；
- 即使把 skills 作为 package data 放进 wheel，也不会自动完成 Codex 或其他 agent 的技能注册。

### 2.9 README 与当前实现漂移

已发现：

- README 说有两个 skill，实际有三个目录；
- skills/ima-note-cli 被描述为主要指导 ima-note，而当前正式入口是 ima；
- 原文章节仍写“用户 URL 探测属于后续批次”，但批次 C 已实施；
- 文件末尾追加了英文 Batch C 小节，没有融入前面的中文结构；
- 项目结构树缺少批次 B/C 新模块；
- 退出码说明未在原有章节完整纳入 9；
- --all、--max-pages、--on-conflict、timeout 的说明集中在末尾补丁；
- pyproject 描述仍只强调“搜索和读取笔记”，没有知识库和写入能力。

### 2.10 缺少自动一致性门禁

当前没有自动检查：

- active skill 数量；
- skill folder 与 frontmatter name；
- frontmatter 只含 name/description；
- SKILL.md 行数；
- agents/openai.yaml；
- skill version；
- CLI parser 与 CLI reference；
- README/skill 中是否仍出现旧 endpoint；
- Markdown 本地链接和 anchor；
- third_party manifest；
- wheel 分发声明；
- 根目录是否重新出现 (1) 下载目录。

## 3. 当前问题

### 3.1 多个 active skill 让触发和行为不确定

ima-note-cli、ima-note 和 ima-skills-1.1.2 同时位于 skills 下。

风险：

- agent 不知道应该加载哪一个；
- 旧 endpoint 可能覆盖新行为；
- 一个 skill 建议使用 Python CLI，另一个建议直接拼 API；
- 凭证、安全和错误规则不一致；
- 更新时需要同步多份文档。

### 3.2 skill 名、版本与 API 契约版本被混为一谈

当前同时存在：

- 项目包版本 0.1.0；
- 上游 skill 版本 1.1.7；
- 旧上游版本 1.1.2；
- ima-note _meta 版本 1.0.1；
- canonical ima-note-cli 没有独立版本。

如果不区分：

- 用户会把 1.1.7 误认为 CLI 版本；
- skill 更新无法判断是否与当前 CLI 匹配；
- 上游 API 契约更新与本项目 skill 文案更新不能独立演进。

### 3.3 上游来源和许可证只有非结构化证据

MIT-0、发布者和来源目前只存在于 skill-card.md 和 _meta.json。

缺少：

- 仓库级 third-party notice；
- 独立许可证文本；
- 原始文件 manifest；
- 原始文件总摘要；
- 导入日期和导入用途；
- “只读归档、非 active、非 wheel 内容”的机器字段。

### 3.4 直接复制上游 1.1.7 会恢复已拒绝的行为

上游包含：

- Node.js/CJS 运行时；
- 自更新检查；
- 任意 Base URL 相关逻辑；
- 直接向 API 发送 JSON；
- 与 Python CLI 不同的错误、重试和输出；
- 未经项目裁决的文档歧义。

因此上游只能作为 provenance 和 contract input，不能覆盖 canonical skill。

### 3.5 旧 skill 删除前缺少迁移清单

若直接删除 ima-note 和 1.1.2，可能丢失：

- 新建与追加必须区分的安全提示；
- 本地图片规则；
- 文件上传命名与重名 Gate；
- Notes/Knowledge 跨模块路由提示；
- 平台编码注意事项；
- API reference 的来源证据。

需要逐项标记“迁入 canonical、由 CLI 实现、归档、明确不采用”。

### 3.6 wheel 与 skill discovery 是两个不同问题

把 skill 文件放进 wheel：

- 只会把文件复制进 site-packages；
- 不会自动注册到 ~/.codex/skills 或其他 agent 目录；
- 会增加 package data 和版本同步负担；
- 可能让用户误以为安装 CLI 等于安装 skill。

不做明确裁决会让 README、包内容和用户预期继续不一致。

### 3.7 CLI help 是实时事实源，README 和 skill 仍手工维护

当前命令和参数来自 argparse parser，但：

- README 命令列表手工编写；
- skill 命令列表手工编写；
- 没有生成的 CLI_REFERENCE；
- 批次 C 只能在文件末尾追加补充；
- 新命令或参数很容易只更新一处。

### 3.8 doc_id 兼容说明容易被误判为正式字段

当前代码仍有经过设计的兼容层：

- --doc-id 是 deprecated alias；
- JSON 暂时输出 doc_id；
- 内部正式字段是 note_id。

一致性检查不能简单禁止所有 doc_id，而应：

- 禁止 docid；
- 禁止旧 endpoint；
- 允许 doc_id 只出现在兼容说明和兼容测试；
- 要求同一处同时明确 note_id 是 canonical。

### 3.9 Markdown 链接随文件移动会失效

阶段 6 会：

- 移动上游目录；
- 合并契约文档；
- 删除两个 skill；
- 新增 CLI reference；
- 更新 README。

没有链接检查时，最容易遗留：

- 指向已删除 docs 的相对链接；
- 指向旧 skills 路径的链接；
- 错误 anchor；
- third_party 内外路径混淆。

### 3.10 历史计划与正式当前路径需要区分

BATCH_A/B/C 实施计划多处记录 ima-skills-1.1.7 (1) 和旧 skill 路径。

这些记录有历史价值，但阶段 6 完成后：

- 正式来源路径必须统一为 third_party/ima-skills/1.1.7；
- 如果保留原下载名，必须明确它只是 intake 时的原始名称；
- 当前验证命令不能继续依赖已删除路径；
- 文档检查不能把历史描述误判为 active 指令。

## 4. 实现原则与已选策略

### 4.1 唯一 canonical skill

确定：

~~~text
skills/ima-note-cli
~~~

为唯一 canonical active skill。

理由：

- 与项目名称和正式入口一致；
- 已有合法 name/description frontmatter；
- 已覆盖 Notes 与 Knowledge；
- 已使用当前 CLI 命令而不是旧 API；
- 适合安装、配置、日常使用和故障排查场景；
- 194 行，适合在 500 行限制内继续维护。

完成后，skills 下只有该 skill 目录和项目级 manifest.json。

### 4.2 ima-note 与 1.1.2 的去向

skills/ima-note：

1. 建立迁移矩阵；
2. 将独有且仍正确的安全意图迁入 canonical skill；
3. 不迁移 raw endpoint 表和直接 API 请求模板；
4. 删除 SKILL.md、_meta.json 和 references；
5. README 明确 ima-note 只保留为 legacy CLI executable，不再是独立 skill。

skills/ima-skills-1.1.2：

1. 用旧标识扫描证明其能力已由当前代码/契约替代；
2. 不把它再复制到 third_party；
3. 删除整个 tracked 目录；
4. 由 Git 历史和迁移文档保留历史；
5. 禁止 active 文档再引用其 endpoint。

不保留 redirect/tombstone SKILL.md，因为它仍可能被 skill discovery 识别为第二个 active skill。

### 4.3 上游 1.1.7 只读归档

规范路径：

~~~text
third_party/ima-skills/1.1.7/original
~~~

归档要求：

- 原始文件按字节移动，不改行尾、不格式化、不修正文案；
- 先对原下载目录生成 SHA-256，再移动；
- SHA256SUMS 使用相对 original 的 POSIX 路径并按路径排序；
- hash 使用原始 bytes；
- 生成 aggregate_manifest_sha256；
- UPSTREAM.json 指向 manifest；
- 原始 (1) 目录在校验成功后删除；
- third_party 不进入 active skill discovery；
- third_party 不进入 wheel；
- 原始 CJS 不执行；
- 原始 SKILL.md 不作为当前安全指导。

### 4.4 上游元数据模型

third_party/ima-skills/1.1.7/UPSTREAM.json 至少包含：

~~~json
{
  "schema_version": 1,
  "name": "ima-skills",
  "version": "1.1.7",
  "slug": "ima-skills",
  "publisher": {
    "name": "iampennyli",
    "owner_id": "..."
  },
  "source_url": "https://clawhub.ai/iampennyli/ima-skills",
  "published_at_ms": 0,
  "recorded_at": "YYYY-MM-DD",
  "license": "MIT-0",
  "license_evidence": "original/skill-card.md",
  "manifest": "SHA256SUMS",
  "aggregate_manifest_sha256": "...",
  "role": "reference-only",
  "active_skill": false,
  "included_in_wheel": false
}
~~~

规则：

- published_at_ms 保留原始整数；
- 如转换 ISO 时间，同时保留原始值；
- recorded_at 表示纳入仓库的日期，不伪造下载日期；
- owner_id 来自 _meta.json；
- source_url 来自 skill-card.md；
- license 来自 skill-card.md；
- 不把本项目作者写成上游作者；
- 不把上游版本写成 CLI 版本。

### 4.5 MIT-0 保存方式

新增：

~~~text
third_party/ima-skills/1.1.7/LICENSE.MIT-0
THIRD_PARTY_NOTICES.md
~~~

要求：

- LICENSE.MIT-0 使用 SPDX 的标准 MIT-0 文本；
- THIRD_PARTY_NOTICES.md 记录项目名称、版本、发布者、来源、许可证和归档路径；
- skill-card.md 继续作为原始许可证证据；
- 明确 MIT-0 只适用于归档的上游内容；
- pyproject 中项目自身 MIT 声明与上游 MIT-0 分开；
- 项目根 LICENSE 的补齐仍属于阶段 7，不在本阶段伪装完成。

本计划不提供法律意见；实施时只进行来源和许可证文本的准确保存。

### 4.6 skill 版本模型

新增 skills/manifest.json，区分三个版本：

~~~json
{
  "schema_version": 1,
  "canonical_skill": "ima-note-cli",
  "skills": [
    {
      "name": "ima-note-cli",
      "path": "skills/ima-note-cli",
      "skill_version": "1.0.0",
      "contract_version": "1.1.7",
      "tested_cli_version": "0.1.0",
      "distribution": "repository-only"
    }
  ]
}
~~~

语义：

- skill_version 是本项目 agent skill 的独立语义版本；
- contract_version 是 IMA API/上游契约版本；
- tested_cli_version 与 ima_note_cli.__version__ 对齐；
- distribution 固定为 repository-only；
- 不在 SKILL.md frontmatter 增加 version；
- 不复用上游 _meta.json 作为 canonical metadata。

初次 canonical 化时 skill_version 从 1.0.0 开始。以后：

- 文案修正可 patch；
- 新 workflow 可 minor；
- 触发条件或行为不兼容可 major；
- CLI 每次发布至少更新 tested_cli_version 或由 checker 明确提示。

### 4.7 canonical SKILL.md 规范

skills/ima-note-cli/SKILL.md 必须：

- frontmatter 只有 name 和 description；
- name 等于 ima-note-cli；
- description 同时说明能力和触发场景；
- 正文使用命令式/不定式；
- 控制在 500 行内；
- 不复制完整 OpenAPI schema；
- 不包含 README、安装指南或 changelog 等额外 skill 内文档；
- 不要求 Node.js；
- 不建议任意 Base URL；
- 不执行 skill 自更新；
- 不请求用户把长期凭证放进命令行；
- 正式推荐 ima；
- 将 ima-note 明确为 legacy executable；
- 将 note_id 明确为 canonical；
- --doc-id/doc_id 只作为兼容说明；
- 包含追加笔记、上传、URL、原文和敏感信息的安全边界；
- 提醒以 ima ... --help 为命令参数事实源；
- 明确 CLI wheel 与 skill 安装是两个步骤。

### 4.8 agents/openai.yaml

使用 skill-creator 提供的 generate_openai_yaml.py 生成，不手写随意字段。

仅生成：

- interface.display_name；
- interface.short_description；
- interface.default_prompt。

约束：

- 所有字符串加引号；
- short_description 为 25 至 64 个字符；
- default_prompt 为简短一句话；
- default_prompt 必须显式包含 $ima-note-cli；
- 不增加 icon、brand_color；
- 不声明不存在的 MCP 或其他工具依赖；
- 不修改 allow_implicit_invocation，使用默认 true；
- 更新 SKILL.md 后检查 openai.yaml 是否仍匹配。

建议语义：

- display_name：IMA Note CLI；
- short_description：安装、配置并安全使用 IMA 笔记与知识库 CLI；
- default_prompt：使用 $ima-note-cli 帮我安装、配置或运行 IMA CLI 命令。

最终字符串以生成器校验结果为准。

### 4.9 唯一规范 API 契约

新增并确定：

~~~text
docs/IMA_OPENAPI_CONTRACT_1_1_7.md
~~~

为唯一规范契约。

合并内容：

- Notes 六个 endpoint；
- Knowledge 十个核心 endpoint；
- wire envelope；
- note_id 兼容层；
- HTTP、错误和重试；
- media 原文；
- 用户 URL；
- 上传 Gate；
- JSON/partial；
- 已知歧义和 smoke 状态；
- fixture 关系；
- 上游 provenance 链接。

完成后删除：

- docs/API_CONTRACT_1_1_7.md；
- docs/KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md。

层级规则：

1. 规范文档：docs/IMA_OPENAPI_CONTRACT_1_1_7.md；
2. 可执行证明：src、tests、fixtures；
3. 用户说明：README；
4. agent workflow：skills/ima-note-cli/SKILL.md；
5. 原始证据：third_party/ima-skills/1.1.7/original。

README 和 skill 不再复制 endpoint 响应表。third_party 文档不得被称为当前规范。

### 4.10 CLI help 与生成文档

新增 tools/render_cli_reference.py。

事实源：

~~~text
src/ima_note_cli/cli.py 的 build_parser()
~~~

生成：

~~~text
docs/CLI_REFERENCE.md
~~~

生成内容：

- 顶层 help；
- note/kb 子命令列表；
- 所有 leaf command help；
- 参数、choices、required、default；
- deprecated alias；
- 生成命令和“请勿手工修改”标记；
- CLI package version。

命令：

~~~bash
uv run python tools/render_cli_reference.py
uv run python tools/render_cli_reference.py --check
~~~

--check 只比较内存生成结果与文件，不写文件；不一致退出非零。

### 4.11 wheel 分发裁决

本阶段确定：

~~~text
Python wheel 不包含 skills。
~~~

理由：

- wheel 的 package data 不等于 agent skill 注册；
- uv tool install 的目标是安装 ima/ima-note 命令；
- skills 目录有独立发现与升级生命周期；
- 把 skill 复制到 site-packages 不能让 Codex 自动发现；
- repository-only 能避免包内副本与仓库副本再次漂移。

README 必须拆成两条安装路径：

1. CLI 安装：
   - uv tool install；
   - 安装 ima 与 ima-note；
   - 不安装 agent skill。
2. Skill 安装：
   - 从 source checkout 复制或链接 skills/ima-note-cli 到目标 agent 的 skill 目录；
   - 具体 discovery 路径以目标 agent 文档为准；
   - 更新 skill 时更新该目录；
   - 不要求安装 third_party。

pyproject.toml 不增加 package-data。阶段 7 的 wheel smoke 应断言没有 skills/ 和 third_party/。

### 4.12 README 文档策略

README 只保留：

- 产品定位；
- 功能摘要；
- CLI 安装；
- skill 安装边界；
- 凭证；
- 常见命令；
- 安全行为；
- JSON/退出码；
- 开发和测试；
- 指向生成 CLI reference、规范契约和 third-party notice 的链接。

必须删除或重写：

- “自带两个相关 skill”；
- 将 ima-note 当正式主入口的描述；
- “URL 探测属于后续批次”；
- 文件末尾独立英文 Batch C 补丁；
- 过时项目结构；
- 与生成 CLI reference 重复的大段参数表。

### 4.13 不重复 API reference

canonical skill 不保留 references/api.md。

理由：

- raw API reference 会与代码裁决再次漂移；
- agent 使用本项目时应运行 CLI，不应绕过 HTTP、安全和输出层；
- 完整 schema 已在唯一契约与 fixtures 中；
- skill 保持短小并依赖 CLI help。

上游 raw references 只在 third_party 归档中保留。

### 4.14 历史计划处理

BATCH_A/B/C_IMPLEMENTATION_PLAN.md 保留实施时的历史描述。

处理规则：

- 不批量重写所有历史问题和验收状态；
- 在文件开头增加“来源路径已在阶段 6 归档”的短注；
- 把仍作为当前命令执行的路径改为 third_party 正式路径；
- 原始 intake 名称 ima-skills-1.1.7 (1) 可在历史说明中保留一次，并明确不是正式路径；
- 当前 README、契约、验证脚本和 skill 不得使用 (1)；
- consistency checker 对历史计划采用单独 allowlist。

### 4.15 无新生产依赖

实现以下功能均使用标准库：

- JSON metadata；
- SHA-256；
- Markdown link 提取；
- heading anchor；
- argparse help 生成；
- frontmatter 简单解析；
- subprocess/check 模式；
- wheel ZIP 内容的一次性验收。

不新增：

- PyYAML；
- markdown-link-check；
- Node.js；
- npm 包；
- production package。

agents/openai.yaml 由 skill-creator 提供的生成器产生；仓库 checker 只验证本阶段使用的确定字段，不实现通用 YAML parser。

## 5. 详细实施步骤

### S6.0.1 建立阶段 6 决策文档

新增 docs/SKILL_DISTRIBUTION_POLICY.md。

内容：

- canonical skill；
- active 与 archive 定义；
- skill/contract/CLI version；
- wheel policy；
- 安装边界；
- 更新责任；
- 事实源层级；
- 不采用上游 CJS 的理由；
- 阶段 7 的后续责任。

验收：

- 对“为什么只有一个 skill”有明确答案；
- 对“uv tool install 是否安装 skill”有明确答案；
- 对“第三方资料是不是当前规范”有明确答案。

### S6.0.2 建立迁移矩阵

新增 docs/SKILL_MIGRATION_1_1_7.md。

按旧资产逐项登记：

| 来源 | 内容 | 处理 | 目标/理由 |
| --- | --- | --- | --- |
| skills/ima-note | 创建/追加安全 | 迁移 | canonical skill |
| skills/ima-note | raw API 表 | 不迁移 | 唯一契约 |
| skills/ima-skills-1.1.2 | 旧 endpoint | 删除 | 已被 1.1.7 替代 |
| 1.1.2 CJS | 上传流程 | 不作为运行时 | Python 服务已实现 |
| upstream 1.1.7 | 原始 references | 归档 | provenance |
| upstream 1.1.7 | 自更新/Base URL | 明确不采用 | 安全边界不同 |

每项必须有 owner 和验证证据。

### S6.0.3 冻结当前 skill/README 兼容基线

实施删除前增加测试：

- ima-note legacy CLI 仍存在；
- --doc-id 兼容仍存在；
- note_id 是正式字段；
- canonical skill 覆盖所有顶层命令；
- README 现有安装命令保持；
- current parser help 可生成。

删除旧 skill 不能被误当作删除 legacy executable。

### S6.1.1 计算上游原始 SHA-256

对 ima-skills-1.1.7 (1)：

1. 验证 resolved source 位于工作区根目录；
2. 列出全部普通文件；
3. 拒绝 symlink、junction、超出目录的路径；
4. 对原始 bytes 计算 SHA-256；
5. 使用正斜杠相对路径排序；
6. 生成临时 manifest；
7. 计算 manifest 自身 SHA-256；
8. 在移动前后各验证一次。

不对原始文件执行格式化、换行转换或 JSON 重写。

### S6.1.2 规范化并移动上游目录

目标：

~~~text
third_party/ima-skills/1.1.7/original
~~~

安全要求：

- 移动前验证 source 和 target 的绝对路径均在工作区；
- target 不存在；
- 不执行覆盖；
- 移动后文件数、相对路径和 hash 完全一致；
- 校验成功后根目录不再有 (1)；
- Git 状态只显示预期新增/删除。

### S6.1.3 写入上游结构化元数据

新增 UPSTREAM.json。

字段从：

- original/_meta.json；
- original/meta.json；
- original/skill-card.md；
- OPTIMIZATION_PLAN 的 intake 日期；
- SHA256SUMS。

读取。

不得：

- 从文件名猜版本；
- 把当前日期冒充 publishedAt；
- 把 Codex/Aimer 写成上游发布者；
- 省略 license evidence。

### S6.1.4 保存 MIT-0 与 third-party notice

新增：

- third_party/ima-skills/1.1.7/LICENSE.MIT-0；
- THIRD_PARTY_NOTICES.md。

验证：

- license ID 精确为 MIT-0；
- notice 链接到归档路径；
- 来源 URL 与 skill-card 一致；
- 不把项目自身许可证改为 MIT-0；
- Markdown 链接通过。

### S6.1.5 增加 manifest 验证

tools/check_repository_docs.py 增加：

- 读取 UPSTREAM.json；
- 校验 version/path；
- 读取 SHA256SUMS；
- 校验 sorted/no duplicate；
- 重新计算每个文件 hash；
- 校验没有 manifest 未登记的 original 文件；
- 校验 aggregate hash；
- 校验 role、active_skill、included_in_wheel。

### S6.2.1 新增 skills/manifest.json

记录：

- 唯一 canonical skill；
- skill version；
- contract version；
- tested CLI version；
- distribution；
- SKILL path；
- agents metadata path。

测试：

- JSON schema_version；
- 唯一性；
- semver 格式；
- folder/name 对齐；
- tested_cli_version 与当前 __version__；
- contract 文件版本；
- repository-only 与 pyproject 一致。

### S6.2.2 重写 canonical frontmatter

skills/ima-note-cli/SKILL.md frontmatter：

- 仅 name；
- description；
- 无 metadata/homepage/version。

description 应覆盖：

- 安装；
- 凭证；
- Notes；
- Knowledge；
- 原文；
- URL/文件上传；
- 故障排查；
- legacy ima-note。

触发场景全部放在 description，不新增“何时使用”正文。

### S6.2.3 整理 canonical 正文

建议结构：

1. Quick start；
2. Install CLI；
3. Install/use skill boundary；
4. Credentials；
5. Read workflows；
6. Write workflows；
7. Upload and URL safety；
8. JSON and exit codes；
9. Legacy compatibility；
10. Troubleshooting；
11. Verify with --help。

迁入：

- 明确创建与追加；
- 追加前明确目标；
- 本地图片过滤；
- note_id；
- 上传命名和冲突；
- URL SSRF；
- 原文 URL/headers；
- UTF-8；
- partial 9。

移除：

- raw endpoint payload；
- raw API response paths；
- Node/CJS；
- 任意 Base URL；
- 自更新；
- 重复 OS 安装长表；
- 与 README 完全重复的开发说明。

### S6.2.4 生成 agents/openai.yaml

实施步骤：

1. 阅读完成后的 SKILL.md；
2. 使用 skill-creator scripts/generate_openai_yaml.py；
3. 传入 display_name；
4. 传入 short_description；
5. 传入 default_prompt；
6. 不传图标、颜色和 MCP；
7. 运行 repo checker；
8. 人工确认文案与 SKILL description 一致。

### S6.2.5 运行 skill-creator quick validation

执行：

~~~bash
python C:/Users/Max/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ima-note-cli
~~~

此路径只作为当前开发环境的辅助验证，不写入项目运行时或 README。仓库自身仍必须有可移植 checker。

### S6.2.6 forward-test canonical skill

在静态检查后，用最小上下文独立验证：

1. “安装 ima 并检查命令”；
2. “配置 Windows 凭证但不要显示值”；
3. “创建而不是追加一篇笔记”；
4. “上传一个远程 PDF 到知识库”；
5. “解释 ima-note 和 --doc-id 是否仍可用”；
6. “解析 exit 9 JSON”。

要求：

- 只提供 skill 和用户请求；
- 不提供预期答案；
- 不使用真实凭证；
- 不发真实网络请求；
- 检查是否推荐正式 ima 命令；
- 检查是否错误绕过 Python CLI；
- 检查是否泄露凭证或建议不安全 Base URL。

### S6.3.1 迁移 ima-note 有效内容

逐项对照 docs/SKILL_MIGRATION_1_1_7.md。

只有以下类型可以迁入：

- 用户意图路由；
- 写入前确认；
- 安全边界；
- CLI 已支持的 workflow。

以下不迁入：

- 直接 ima_api 调用；
- API schema；
- 与 canonical contract 冲突的 error code；
- WebFetch/外部命令依赖；
- 未由 CLI 实现的功能。

### S6.3.2 删除 skills/ima-note

删除：

- skills/ima-note/SKILL.md；
- skills/ima-note/_meta.json；
- skills/ima-note/references/api.md；
- 空目录。

完成后：

- README 不再称其为 active skill；
- ima-note executable 仍有测试；
- skill checker 只发现一个 SKILL.md；
- Git history 保留删除前内容。

### S6.3.3 验证并删除 1.1.2

删除前扫描：

~~~text
search_note_book
list_note_folder_by_cursor
list_note_by_folder_id
docid
~~~

要求这些 token 只存在于：

- 历史迁移文档；
- 必要的负向测试；
- third_party 原始归档。

然后删除 skills/ima-skills-1.1.2。

不将旧 CJS 复制到 canonical skill。

### S6.4.1 合并规范契约

新增 docs/IMA_OPENAPI_CONTRACT_1_1_7.md。

合并时：

- 保留所有已裁决接口；
- 保留待 smoke 项；
- 保留 Batch C addendum；
- 统一中文标题；
- 删除“批次 A/B/C addendum”式历史拼接；
- 按当前架构重排；
- 链接 third_party provenance；
- 链接 fixtures；
- 不复制上游全文；
- 不把未验证问题写成已确认。

### S6.4.2 更新所有契约链接

更新：

- README；
- OPTIMIZATION_PLAN；
- BATCH_A/B/C 当前引用；
- fixture README；
- canonical skill 中如有链接；
- third-party notice；
- 新 policy/migration 文档。

完成后删除两份旧 contract 文件。

### S6.4.3 生成 CLI reference

新增 tools/render_cli_reference.py 和 docs/CLI_REFERENCE.md。

生成器：

- 直接 import build_parser；
- 递归遍历 parser/subparser；
- 保持 argparse format_help；
- 规范 LF；
- 输出稳定排序；
- 不读取凭证；
- 不访问网络；
- 不创建 client；
- --check 不写文件。

### S6.4.4 更新 README

按以下顺序重构：

1. 项目说明；
2. 功能；
3. CLI 与 skill 分发说明；
4. CLI 安装；
5. skill 安装；
6. 凭证；
7. 常见 workflow；
8. 安全边界；
9. JSON/退出码；
10. 开发测试；
11. 文档索引；
12. third-party notice。

必须：

- 只有一个 canonical skill；
- 主入口为 ima；
- ima-note 标 legacy；
- note_id 正式；
- doc_id 兼容；
- URL 探测写成已实现；
- 上传和分页写进相应正式章节；
- exit 9 纳入退出码表；
- 移除末尾独立英文 Batch C 小节；
- 项目结构反映 commands、service、remote/cos/pagination；
- 链接生成 CLI reference；
- 明确 wheel 不含 skill。

### S6.4.5 更新 pyproject 描述

修改：

~~~toml
description
keywords
~~~

使其覆盖：

- Notes；
- Knowledge base；
- read/write；
- CLI。

不在本阶段：

- 改版本来源；
- 增加 project URLs；
- 改 license 语法；
- 加 package data；
- 加依赖。

这些属于阶段 7。

### S6.4.6 更新历史计划的来源注记

在 BATCH_A/B/C 顶部增加：

~~~text
阶段 6 注：当时的 intake 路径 ima-skills-1.1.7 (1) 已归档为
third_party/ima-skills/1.1.7/original；原计划中的旧路径只表示历史基线。
~~~

将仍会执行的验证命令改用当前路径；历史描述可保留。

### S6.5.1 实现 Markdown 链接检查

tools/check_repository_docs.py 检查 active Markdown：

- README.md；
- docs/**/*.md；
- skills/ima-note-cli/SKILL.md；
- BATCH/STAGE/OPTIMIZATION 计划；
- THIRD_PARTY_NOTICES.md。

检查：

- 相对文件存在；
- 路径不逃出仓库；
- fragment 对应 heading；
- URL decode 后仍在仓库；
- Windows/Unix separator 一致；
- 链接不指向已删除 skill；
- 链接不指向 (1)；
- archive Markdown 可单独检查其内部相对链接。

外部 HTTP(S) 链接只做语法检查，不在单测访问网络。

### S6.5.2 实现 canonical skill 检查

检查：

- skills/manifest.json 存在；
- canonical 只有一个；
- skills 下只有 manifest 和 canonical dir；
- SKILL.md 存在；
- frontmatter 以 --- 开始结束；
- 只有 name/description；
- folder/name 一致；
- description 非空；
- 正文少于 500 行；
- agents/openai.yaml 存在；
- display_name/short_description/default_prompt；
- default_prompt 含 $ima-note-cli；
- 无 icon/brand/dependency 非授权字段；
- 不含 Node/CJS、IMA_BASE_URL、自更新指令；
- 不含旧 endpoint/docid。

### S6.5.3 实现命令与文档一致性检查

以 parser 为源：

- 生成 leaf command 清单；
- 与 docs/CLI_REFERENCE.md 完全比较；
- 检查 canonical skill 覆盖每个 leaf command；
- 检查 README 覆盖每个顶层 workflow；
- 检查关键 options：
  - --json；
  - --note-id；
  - --doc-id deprecated；
  - --all；
  - --max-pages；
  - --on-conflict；
  - --download-timeout；
  - --upload-timeout；
  - --force。

不要求 README 复制每个 argparse help 行；完整参数只由 generated reference 承担。

### S6.5.4 实现字段和 endpoint 漂移检查

active surfaces 禁止：

- search_note_book；
- list_note_folder_by_cursor；
- list_note_by_folder_id；
- docid；
- 1.1.2；
- ima-skills-1.1.7 (1) 正式路径；
- “URL 探测属于后续批次”。

doc_id 采用上下文 allowlist：

- 允许 deprecated/compatibility 描述；
- 允许测试兼容层；
- 要求同段出现 note_id/canonical；
- 禁止把 doc_id 写成当前 API request 的正式字段。

archive 和迁移文档可包含旧 token。

### S6.5.5 实现分发策略检查

检查：

- pyproject packages.find 仍仅为 src；
- 无 package-data 包含 skills/third_party；
- skills/manifest distribution 为 repository-only；
- README 明确 CLI 安装不安装 skill；
- canonical skill 不声称自己位于 wheel；
- third_party UPSTREAM included_in_wheel=false。

阶段 6 完成时额外进行一次临时 wheel 检查：

1. 构建到系统临时目录；
2. 用 zipfile 枚举 wheel；
3. 断言无 skills/、third_party/、上游 CJS；
4. 断言 ima_note_cli 包和 entry point 存在；
5. 删除临时目录。

这是一项验收，不替代阶段 7 CI。

### S6.5.6 新增仓库一致性测试

新增 tests/test_repository_docs.py。

测试：

- canonical skill；
- manifest；
- CLI reference；
- active links；
- old token；
- upstream manifest；
- distribution policy；
- README critical statements。

所有测试：

- 无网络；
- 无真实凭证；
- 不依赖当前用户 home；
- 不修改仓库；
- Windows/Linux 路径一致；
- 失败信息给出文件和行号。

### S6.5.7 提供统一检查命令

阶段 6 提供：

~~~bash
uv run python tools/check_repository_docs.py
uv run python tools/render_cli_reference.py --check
uv run python -m unittest tests.test_repository_docs -v
~~~

阶段 7 再把它们接入 CI/check 聚合。

### S6.6.1 更新总计划

修改 OPTIMIZATION_PLAN.md：

- 链接本实施计划；
- 将来源路径改为规范 archive；
- 阶段完成后勾选阶段 6；
- 更新仓库基线中的 skill 数量；
- 更新 wheel policy；
- 保留阶段 7 未完成项。

### S6.6.2 执行全量回归

执行：

- 127 个现有测试；
- 新 consistency tests；
- compileall；
- CLI help check；
- skill quick validation；
- manifest；
- Markdown；
- 临时 wheel inventory；
- git diff --check；
- git status。

### S6.6.3 最终人工审阅

人工确认：

- README 安装步骤真实；
- canonical skill 没有绕过 CLI；
- third-party attribution 清晰；
- MIT 与 MIT-0 不混淆；
- old skills 完全退出 active；
- 历史计划仍可理解；
- stage 7 边界没有被提前实现。

## 6. 涉及文件

### 6.1 新增文件

| 文件 | 用途 |
| --- | --- |
| STAGE_6_IMPLEMENTATION_PLAN.md | 本计划 |
| docs/IMA_OPENAPI_CONTRACT_1_1_7.md | 唯一规范 API 契约 |
| docs/CLI_REFERENCE.md | 从 parser 生成的完整 CLI 参考 |
| docs/SKILL_DISTRIBUTION_POLICY.md | canonical、版本和 wheel 裁决 |
| docs/SKILL_MIGRATION_1_1_7.md | 旧 skill 迁移矩阵 |
| THIRD_PARTY_NOTICES.md | 上游归属和许可证索引 |
| skills/manifest.json | canonical skill registry/version |
| skills/ima-note-cli/agents/openai.yaml | UI 元数据 |
| third_party/ima-skills/1.1.7/UPSTREAM.json | 结构化上游元数据 |
| third_party/ima-skills/1.1.7/SHA256SUMS | 原始文件 SHA-256 |
| third_party/ima-skills/1.1.7/LICENSE.MIT-0 | 上游许可证文本 |
| third_party/ima-skills/1.1.7/original/** | 原 1.1.7 文件的字节级归档 |
| tools/render_cli_reference.py | CLI reference 生成/check |
| tools/check_repository_docs.py | skill/docs/provenance 一致性 |
| tests/test_repository_docs.py | 离线一致性回归 |

### 6.2 修改文件

| 文件 | 修改 |
| --- | --- |
| OPTIMIZATION_PLAN.md | 链接本计划和更新正式路径 |
| README.md | 单 skill、分发、当前功能和文档索引 |
| pyproject.toml | description/keywords，与当前功能一致 |
| skills/ima-note-cli/SKILL.md | canonical 化、精简和当前命令 |
| BATCH_A_IMPLEMENTATION_PLAN.md | 阶段 6 归档注记 |
| BATCH_B_IMPLEMENTATION_PLAN.md | 阶段 6 归档注记 |
| BATCH_C_IMPLEMENTATION_PLAN.md | 阶段 6 归档注记 |
| tests/fixtures/notes/README.md | 指向唯一契约 |
| tests/fixtures/knowledge/README.md | 指向唯一契约 |
| tests/fixtures/url_ingest/README.md | 指向唯一契约 |

如果其他 Markdown 链接检查失败，只修改引用，不借机重写无关历史内容。

### 6.3 移动文件

~~~text
ima-skills-1.1.7 (1)/**
  -> third_party/ima-skills/1.1.7/original/**
~~~

移动前后必须 hash 一致。

### 6.4 删除文件

删除 skills/ima-note：

- _meta.json；
- SKILL.md；
- references/api.md。

删除 skills/ima-skills-1.1.2：

- _meta.json；
- SKILL.md；
- notes/**；
- knowledge-base/**。

删除被合并的契约：

- docs/API_CONTRACT_1_1_7.md；
- docs/KNOWLEDGE_MEDIA_CONTRACT_1_1_7.md。

删除根目录原始下载路径：

- ima-skills-1.1.7 (1)，仅在归档校验通过后。

### 6.5 预计无需修改

- src/ima_note_cli 的业务实现；
- src/ima_note_cli/__version__；
- uv.lock；
- 上传、URL 和媒体服务；
- API endpoint；
- fixtures JSON 正文；
- .github/workflows；
- coverage/lint/type 配置；
- 项目根 LICENSE；
- CHANGELOG；
- release/tag。

若 consistency test 暴露真实代码/CLI 漂移，应单独修复并说明，不能为了让文档通过而伪造说明。

## 7. 验收矩阵

### 7.1 canonical skill 唯一性

- [x] skills 下只有 manifest.json 和 ima-note-cli；
- [x] 只有一个 active SKILL.md；
- [x] canonical_skill 精确为 ima-note-cli；
- [x] folder 与 frontmatter name 一致；
- [x] 不保留 redirect/tombstone skill；
- [x] ima-note executable 仍存在，但不再有同名 skill；
- [x] 1.1.2 不在 active 路径。

### 7.2 skill-creator 规范

- [x] SKILL.md frontmatter 只有 name 和 description；
- [x] description 同时描述能力和触发场景；
- [x] 正文为命令式/不定式；
- [x] 总行数小于 500；
- [x] 不包含冗余 API reference；
- [x] 不包含 README/CHANGELOG 等 skill 内辅助文档；
- [x] agents/openai.yaml 存在；
- [x] display_name 正确；
- [x] short_description 为 25 至 64 字符；
- [x] default_prompt 包含 $ima-note-cli；
- [x] 未添加未经请求的 icon、brand_color 和 MCP；
- [x] quick_validate 通过。

### 7.3 skill 内容

- [x] 正式入口为 ima；
- [x] ima-note 标记 legacy；
- [x] note_id 是 canonical；
- [x] --doc-id/doc_id 只标兼容；
- [x] Notes 六个命令覆盖；
- [x] Knowledge 十一个命令覆盖；
- [x] auth 覆盖；
- [x] --json 覆盖；
- [x] --all/--max-pages 覆盖；
- [x] URL 探测和 SSRF 说明覆盖；
- [x] --on-conflict 与 timeout 覆盖；
- [x] 原文 read/export 安全边界覆盖；
- [x] exit 9 覆盖；
- [x] 不建议 raw API、Node/CJS、任意 Base URL 或自更新。

### 7.4 版本模型

- [x] skill_version 与 contract_version 分开；
- [x] tested_cli_version 与 __version__ 一致；
- [x] 上游 1.1.7 不被写成 CLI 版本；
- [x] skill_version 符合 semver；
- [x] manifest schema_version 固定；
- [x] 分发字段为 repository-only；
- [x] checker 能发现任意版本漂移。

### 7.5 上游归档

- [x] 正式路径无 (1)；
- [x] original 文件集合与下载目录一致；
- [x] 每个 SHA-256 移动前后相同；
- [x] SHA256SUMS 排序且无重复；
- [x] aggregate hash 正确；
- [x] UPSTREAM version=1.1.7；
- [x] slug、owner、publisher、source URL 有证据；
- [x] role=reference-only；
- [x] active_skill=false；
- [x] included_in_wheel=false；
- [x] 原始文件未格式化或改行尾；
- [x] 原始 CJS 未被执行。

### 7.6 许可证与归属

- [x] skill-card 原始证据保留；
- [x] LICENSE.MIT-0 存在；
- [x] THIRD_PARTY_NOTICES 有发布者、来源、版本和路径；
- [x] MIT-0 与项目 MIT 清晰分开；
- [x] 不把项目作者当上游作者；
- [x] 不丢失 ClawHub 来源；
- [x] 项目根 LICENSE 缺失仍明确留给阶段 7。

### 7.7 旧 skill 迁移

- [x] ima-note 有逐项迁移记录；
- [x] 安全意图已迁入或由 CLI 明确实现；
- [x] raw API 表未复制进 canonical；
- [x] 1.1.2 有删除证据；
- [x] 旧 endpoint 不在 active docs/skill；
- [x] 旧 CJS 不成为运行时；
- [x] Git history 足以追溯删除内容；
- [x] README 不再列两个或三个 active skill。

### 7.8 唯一契约

- [x] docs/IMA_OPENAPI_CONTRACT_1_1_7.md 存在；
- [x] Notes、Knowledge、媒体、URL、上传和 JSON 均在其中；
- [x] 两份旧 contract 已删除；
- [x] active skill 无 API schema 副本；
- [x] README 无 endpoint 响应表副本；
- [x] third_party 明确为 evidence-only；
- [x] fixtures README 均链接唯一契约；
- [x] 当前代码/测试与契约无已知冲突。

### 7.9 CLI reference

- [x] docs/CLI_REFERENCE.md 标记 generated；
- [x] 所有 leaf command 存在；
- [x] 所有关键 option 存在；
- [x] default/choices/required 与 parser 一致；
- [x] --check 在无变更时返回 0；
- [x] 修改 parser 而不生成文档时测试失败；
- [x] 生成器不读凭证、不访问网络；
- [x] 输出在 Windows/Linux 稳定。

### 7.10 README

- [x] 功能与当前 127-test 实现一致；
- [x] 单一 skill；
- [x] CLI 与 skill 安装分开；
- [x] uv tool install 不被描述为安装 skill；
- [x] ima 主入口；
- [x] ima-note legacy；
- [x] 凭证三层优先级正确；
- [x] URL 探测写成已实现；
- [x] 流式上传、conflict、timeout、分页已融入正式章节；
- [x] exit 9 在退出码表；
- [x] 移除末尾英文 Batch C 补丁；
- [x] 项目结构当前；
- [x] 链接 CLI reference、contract 和 notices。

### 7.11 pyproject 与 wheel

- [x] description 包含 Notes 与 Knowledge；
- [x] keywords 与项目能力一致；
- [x] 不新增生产依赖；
- [x] 不增加 skills package data；
- [x] 临时 wheel 无 skills/；
- [x] 临时 wheel 无 third_party/；
- [x] 临时 wheel 无 CJS；
- [x] ima_note_cli 仍存在；
- [x] entry points 仍有 ima 与 ima-note；
- [x] README 对 wheel 内容描述准确。

### 7.12 Markdown 链接

- [x] active Markdown 相对文件链接全部存在；
- [x] fragment 对应 heading；
- [x] 无链接逃出仓库；
- [x] 无 active 链接指向删除 skill；
- [x] 无 active 链接指向 (1)；
- [x] archive 内部链接可解析；
- [x] 外部链接不在离线测试访问；
- [x] 失败包含文件和行号。

### 7.13 漂移检测

- [x] search_note_book 被 active 检查禁止；
- [x] list_note_folder_by_cursor 被禁止；
- [x] list_note_by_folder_id 被禁止；
- [x] docid 被禁止；
- [x] doc_id 只有兼容 allowlist；
- [x] “后续批次 URL 探测”被禁止；
- [x] parser/CLI reference 自动比对；
- [x] skill/manifest/version 自动比对；
- [x] provenance hash 自动比对。

### 7.14 回归和工作区

- [x] 当前 127 个测试继续通过；
- [x] 新测试全部通过；
- [x] compileall 通过；
- [x] 无真实网络和凭证；
- [x] 不修改业务实现；
- [x] uv.lock 无变化；
- [x] git diff --check 通过；
- [x] 不覆盖用户其他工作区修改；
- [x] 阶段 7 内容未提前混入。

## 8. 验证命令

### 8.1 聚焦测试

~~~bash
uv run python -m unittest tests.test_repository_docs -v
uv run python -m unittest tests.test_cli tests.test_cli_batch_b tests.test_cli_batch_c -v
uv run python -m unittest tests.test_notes_api tests.test_knowledge_api -v
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests tools
~~~

### 8.2 生成和一致性

~~~bash
uv run python tools/render_cli_reference.py --check
uv run python tools/check_repository_docs.py
~~~

### 8.3 CLI help

~~~bash
uv run python -m ima_note_cli --help
uv run python -m ima_note_cli note --help
uv run python -m ima_note_cli note search --help
uv run python -m ima_note_cli kb --help
uv run python -m ima_note_cli kb add-url --help
uv run python -m ima_note_cli kb add-file --help
uv run python -m ima_note_cli kb export --help
~~~

### 8.4 静态搜索

~~~bash
rtk rg -n "search_note_book|list_note_folder_by_cursor|list_note_by_folder_id|docid" README.md docs skills src tests
rtk rg -n "ima-skills-1\.1\.7 \(1\)" README.md docs skills tools tests OPTIMIZATION_PLAN.md
rtk rg -n "skills/ima-note\b|skills/ima-skills-1\.1\.2" README.md docs skills tools tests
rtk rg -n "IMA_BASE_URL|check_skill_update|cos-upload\.cjs|preflight-check\.cjs" skills/ima-note-cli
rtk rg -n "doc_id" README.md docs skills/ima-note-cli src tests
rtk rg -n "后续批次|Batch C" README.md skills/ima-note-cli
rtk rg -n "\[[^]]+\]\([^)]+\)" README.md docs skills/ima-note-cli THIRD_PARTY_NOTICES.md
~~~

解释：

- 旧 token 可出现在 third_party 和 migration/history allowlist；
- doc_id 可出现在明确兼容说明和测试；
- canonical skill 中不允许 CJS/Base URL/self-update；
- (1) 只允许在历史 intake 注记中出现。

### 8.5 Git

~~~bash
rtk git diff --check
rtk git status --short
rtk git diff --stat
~~~

### 8.6 临时 wheel inventory

使用系统临时目录构建，不写 dist：

~~~text
TemporaryDirectory
  -> uv build --wheel --out-dir TEMP
  -> zipfile list
  -> assert ima_note_cli exists
  -> assert skills, third_party, *.cjs absent
  -> cleanup
~~~

完整 wheel 安装 smoke 仍由阶段 7 负责。

## 9. 实施顺序与提交切片

### S6-1：决策、安全网和生成器

包含：

- 本计划；
- distribution policy；
- migration matrix；
- manifest schema；
- CLI reference 生成器；
- consistency checker 骨架；
- 删除前兼容测试。

回滚边界：不移动或删除任何 skill。

### S6-2：上游归档与许可证

包含：

- SHA256SUMS；
- third_party 规范路径；
- UPSTREAM.json；
- LICENSE.MIT-0；
- THIRD_PARTY_NOTICES；
- manifest 验证。

回滚边界：可将原始文件按 hash 原样恢复到 intake 路径。

### S6-3：canonical skill

包含：

- SKILL.md；
- agents/openai.yaml；
- skills/manifest.json；
- skill checker；
- quick_validate；
- forward-test。

回滚边界：旧 skill 尚未删除。

### S6-4：迁移并淘汰旧 skill

包含：

- ima-note 内容迁移；
- 删除 skills/ima-note；
- 删除 skills/ima-skills-1.1.2；
- active skill 唯一性测试。

回滚边界：Git 可恢复旧目录，但正常分支不保留 tombstone。

### S6-5：唯一契约与 CLI reference

包含：

- 合并契约；
- 删除旧 contract；
- fixture README；
- 生成 CLI_REFERENCE；
- link checker。

回滚边界：先更新所有链接再删除旧文件。

### S6-6：README、metadata 与分发验证

包含：

- README 重构；
- pyproject description/keywords；
- 历史计划注记；
- wheel inventory；
- 全量测试。

回滚边界：不改变 package version、业务代码或依赖。

每个切片必须保持全量测试通过。上游移动和旧 skill 删除不能与 checker 首次引入混在同一个不可审阅提交中。

## 10. 主要风险与应对

### 风险 1：删除 ima-note 丢失安全指导

应对：

- 先建立迁移矩阵；
- 逐项标记迁入/不采用/由代码实现；
- canonical forward-test；
- 删除后搜索；
- Git 历史保留。

### 风险 2：旧 1.1.2 被外部用户直接引用

应对：

- README 不曾承诺其为稳定公共路径；
- migration 文档记录 replacement；
- 不保留 active redirect skill；
- 发布说明在阶段 7 强调；
- Git tag/history 可追溯。

### 风险 3：上游移动改变原始 bytes

应对：

- 移动前 hash；
- 移动后 hash；
- 禁止格式化；
- raw manifest；
- 文件数和路径比较；
- 不用编辑器重写。

### 风险 4：third_party 中的 SKILL.md 被误认为 active

应对：

- 不位于 skills；
- UPSTREAM role=reference-only；
- README/policy 明确；
- checker 只把 skills 一级 canonical 作为 active；
- 不提供从 third_party 安装的命令。

### 风险 5：MIT 与 MIT-0 混淆

应对：

- 独立 LICENSE.MIT-0；
- third-party notice；
- project license 声明分开；
- 不改 pyproject license；
- 阶段 7 再补项目根 LICENSE。

### 风险 6：frontmatter 校验与上游 metadata 冲突

应对：

- canonical 按 skill-creator 只保留 name/description；
- 上游 extra metadata 原样留 archive；
- UI metadata 放 agents/openai.yaml；
- project version 放 skills/manifest.json。

### 风险 7：skill version 与 CLI version 再次漂移

应对：

- 三版本模型；
- checker 读取 __version__；
- manifest 测试；
- 阶段 7 统一项目版本后继续复用检查。

### 风险 8：CLI reference 生成不稳定

应对：

- 标准库 argparse；
- 固定遍历；
- 规范换行；
- 不包含路径、时间或凭证；
- Windows/Linux fixture；
- check mode。

### 风险 9：README 过度复制 CLI help

应对：

- README 只写 workflow；
- 完整参数由 generated CLI reference；
- canonical skill 依赖 --help；
- checker 只要求关键覆盖，不要求全文复制。

### 风险 10：Markdown anchor 算法误报

应对：

- 实现与 GitHub slug 兼容的有限算法；
- 对复杂显式 anchor 支持；
- 测试中文、英文、重复标题；
- 外部链接不联网；
- 必要时先只检查 file path，再单独启用 anchor，但完成标准要求 anchor 最终通过。

### 风险 11：wheel policy 让用户找不到 skill

应对：

- README 明确双安装；
- canonical skill 在 source checkout 稳定路径；
- 不声称 uv tool 自动安装 skill；
- 后续若要独立分发，单独设计 skill release，而不是偷偷塞进 package data。

### 风险 12：历史计划包含旧路径导致 checker 失败

应对：

- 历史文件 allowlist；
- 顶部归档注记；
- 当前命令使用新路径；
- 不把历史名称当 active link；
- checker 输出上下文。

### 风险 13：合并契约时丢失待验证事项

应对：

- 合并前 section inventory；
- Notes/Knowledge/B/C addendum 对照；
- 待 smoke 表逐项迁移；
- 原文件删除前 diff；
- fixtures README 链接检查。

### 风险 14：canonical skill 仍教 agent 直接 API

应对：

- 禁止 ima_api/raw endpoint 模板；
- forward-test；
- checker 搜索；
- 指导使用 ima commands；
- API contract 只给维护者。

### 风险 15：范围扩张到阶段 7

应对：

- 不加 CI；
- 不加 lint/type/coverage；
- 不统一版本来源；
- 不加项目 root LICENSE；
- 不加 CHANGELOG/tag/release；
- wheel 只做一次 inventory 验收。

## 11. 完成定义

阶段 6 只有在以下条件同时满足时才算完成：

1. skills/ima-note-cli 是唯一 active skill。
2. skills/ima-note 已完成有效内容迁移并删除。
3. skills/ima-skills-1.1.2 已验证淘汰并删除。
4. ima-note legacy executable 仍可用，未与同名 skill 混淆。
5. canonical SKILL.md frontmatter 只有 name 和 description。
6. canonical SKILL.md 少于 500 行并以当前 ima CLI 为唯一工作流入口。
7. agents/openai.yaml 已由 skill-creator 生成并与 SKILL.md 匹配。
8. skills/manifest.json 明确 skill、contract、CLI 三类版本。
9. 上游 1.1.7 已归档到 third_party/ima-skills/1.1.7/original。
10. 根目录不再存在带 (1) 的正式路径。
11. 上游每个原始文件都有 SHA-256 且移动前后相同。
12. UPSTREAM.json 完整记录版本、来源、发布者、时间、许可证和角色。
13. MIT-0 文本和 third-party notice 已保存。
14. 上游归档明确为 reference-only、非 active、非 wheel 内容。
15. docs/IMA_OPENAPI_CONTRACT_1_1_7.md 是唯一规范 API 契约。
16. 两份旧 contract 已安全合并并删除。
17. active skill 和 README 不再复制 raw API schema。
18. docs/CLI_REFERENCE.md 完全由 parser 生成。
19. parser 变化而未更新 reference 时检查失败。
20. README、CLI help、canonical skill 和代码中的正式命令/字段一致。
21. note_id 是唯一正式 ID，doc_id 只在兼容说明中出现，docid/旧 endpoint 被禁止。
22. README 明确 uv tool install 只安装 CLI，不安装 agent skill。
23. pyproject description/keywords 与 Notes + Knowledge 实际能力一致。
24. 临时 wheel 不包含 skills、third_party 或 CJS。
25. Markdown 本地链接和 anchors 全部通过。
26. repository checker 能验证 active skill、metadata、版本、链接、命令和 provenance。
27. 当前 127 个测试继续通过，新增 tests 全部通过。
28. 所有验证离线且不读取真实凭证。
29. 不新增生产依赖，uv.lock 无变化。
30. 不修改业务 API/上传/URL/媒体实现。
31. 不丢失上游 MIT-0、发布者和来源信息。
32. 未提前实施阶段 7 的 CI、项目许可证、版本和发布工作。
33. compileall、quick_validate、wheel inventory、git diff --check 和工作区检查全部通过。

完成阶段 6 后，阶段 7 可以在稳定的单 skill、单契约、明确 wheel 边界上建立 CI、质量门禁、项目许可证、统一版本和发布流程。
