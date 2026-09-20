# CookHero 项目结构详解

本文档详细说明 CookHero 项目的目录结构和各模块职责。

---

## 一、项目根目录

```
CookHero/
├── app/                    # 后端应用主目录
├── frontend/               # 前端应用
├── scripts/                # 工具脚本
├── tests/                  # 测试文件
├── data/                   # 数据目录
├── deployments/            # 部署配置
├── docs/                   # 项目文档
├── config.yml              # 主配置文件
├── .env.example            # 环境变量模板
├── requirements.txt        # Python 依赖
├── README.md              # 中文说明文档
└── .gitignore             # Git 忽略规则
```

---

## 二、后端应用 (`app/`)

### 2.1 API 层 (`app/api/`)

```
api/
└── v1/
    └── endpoints/
        ├── auth.py           # 用户认证接口（注册、登录、令牌刷新）
        ├── conversation.py   # 对话接口（创建、查询、流式响应）
        ├── agent.py          # Agent 接口（智能对话、工具调用、会话管理、子代理管理）
        ├── diet.py           # 饮食管理接口（计划餐次、记录、分析、偏好）
        ├── evaluation.py     # RAG 评估接口（统计、趋势、告警）
        ├── llm_stats.py      # LLM 使用统计接口（含工具统计）
        ├── personal_docs.py  # 个人文档接口（上传、删除、列表）
        └── user.py           # 用户信息接口（获取、更新）
```

**职责**：
- 定义 RESTful API 端点
- 请求验证（Pydantic 模型）
- 调用服务层处理业务逻辑
- 返回标准化响应
- 安全检查集成

---

### 2.2 配置模块 (`app/config/`)

```
config/
├── __init__.py           # 模块初始化和导出
├── config_loader.py      # 配置加载器（从 config.yml 和 .env 加载）
├── config.py             # 全局配置类（Settings）
├── database_config.py    # 数据库配置（PostgreSQL, Redis, Milvus）
├── evaluation_config.py  # RAG 评估配置（RAGAS 指标、采样率、告警阈值）
├── llm_config.py         # LLM 提供商配置（fast/normal 两层）
├── mcp_config.py         # MCP 服务器配置（Amap 等）
├── rag_config.py         # RAG 管道配置（检索参数、重排序）
├── vision_config.py      # 视觉模型和图片生成配置
└── web_search_config.py  # Web 搜索配置（Tavily）
```

**职责**：
- 统一管理项目配置
- 环境变量注入
- 配置验证和默认值处理
- 提供全局 Settings 单例

**配置类**：
- `Settings`: 全局配置入口
- `LLMConfig`: LLM 提供商配置（fast/normal/vision 三层）
- `DatabaseConfig`: 数据库连接配置
- `RAGConfig`: RAG 管道配置
- `VisionConfig`: 视觉模型配置
- `ImageGenerationConfig`: 图片生成配置（DALL-E 3）
- `ImageStorageConfig`: 图片存储配置（imgbb）
- `MCPConfig`: MCP 服务器配置
- `WebSearchConfig`: Web 搜索配置
- `EvaluationConfig`: RAG 评估配置

---

### 2.3 对话管理 (`app/conversation/`)

```
conversation/
├── __init__.py           # 模块初始化和导出
├── types.py              # 类型定义（对话类型、意图类型等）
├── prompts.py            # 系统提示词模板
├── intent.py             # 意图识别（查询、推荐、闲聊等）
├── query_rewriter.py     # 查询改写（优化用户输入）
├── llm_orchestrator.py   # LLM 编排（多模型选择、调用、流式响应）
```

**职责**：
- 理解用户意图
- 优化查询语句
- 管理对话历史和上下文
- LLM 流式响应编排
- 持久化会话数据

---

### 2.4 上下文管理 (`app/context/`)

```
context/
├── __init__.py           # 模块初始化
├── manager.py            # 上下文管理器（构建检索上下文）
└── compress.py           # 上下文压缩（提取关键片段）
```

**职责**：
- 管理对话上下文窗口
- 压缩长文本以节省 token
- 提取最相关的检索结果
- 上下文信息结构化

---

### 2.5 数据库层 (`app/database/`)

```
database/
├── __init__.py           # 模块初始化和公共导出
├── models.py             # ORM 模型（User, Conversation, Message, RAGEvaluation, LLMUsageLog）
├── session.py            # 数据库会话管理（连接池、事务）
├── conversation_repository.py  # 对话仓库（CRUD）
├── document_repository.py      # 文档仓库（元数据缓存、CRUD）
├── evaluation_repository.py    # 评估仓库（RAG 评估记录 CRUD）
└── llm_usage_repository.py     # LLM 使用记录仓库（统计查询）
```

**职责**：
- 定义数据表结构（SQLAlchemy ORM）
- 管理数据库连接（PostgreSQL）
- 提供数据访问接口
- LLM 使用统计查询

---

### 2.6 LLM 提供商 (`app/llm/`)

```
llm/
├── __init__.py           # 模块初始化和导出
├── provider.py           # LLM 提供者和调用器（LLMProvider, LLMInvoker）
├── context.py            # LLM 调用上下文管理（contextvars 实现）
└── callbacks.py          # 回调处理器（Token 使用追踪、工具名称提取）
```

**职责**：
- 统一 LLM 调用接口
- 支持多模型切换和随机选择（负载均衡）
- Token 使用量追踪和持久化
- 调用上下文管理（module_name, user_id, conversation_id）
- 工具调用名称提取和记录

**核心类**：
- `LLMProvider`: 全局 LLM 提供者，管理配置和创建实例
- `LLMInvoker`: LLM 调用器，封装调用逻辑和 usage tracking
- `LLMCallContext`: 调用上下文信息
- `LLMUsageCallbackHandler`: Token 使用回调处理器

---

### 2.7 RAG 核心模块 (`app/rag/`)

#### 2.7.1 缓存系统 (`app/rag/cache/`)

```
cache/
├── __init__.py           # 模块初始化
├── base.py               # 缓存基类
├── backends.py           # Redis 和 Milvus 缓存后端实现
└── cache_manager.py      # 缓存管理器（L1+L2 双层缓存）
```

**职责**：
- L1 缓存（Redis）：精确匹配查询
- L2 缓存（Milvus）：语义相似查询
- 缓存失效和更新策略
- 缓存命中率统计

#### 2.7.2 嵌入模型 (`app/rag/embeddings/`)

```
embeddings/
├── __init__.py           # 模块初始化
└── embedding_factory.py  # 嵌入模型工厂（HuggingFace, OpenAI）
```

**职责**：
- 加载和管理嵌入模型
- 文本向量化
- 支持多种嵌入模型后端

#### 2.7.3 检索管道 (`app/rag/pipeline/`)

```
pipeline/
├── __init__.py           # 模块初始化
├── retrieval.py          # 检索模块（向量检索、BM25、混合检索）
├── generation.py         # 生成模块（LLM 答案生成）
├── metadata_filter.py    # 元数据过滤（烹饪时间、难度等）
└── document_processor.py # 文档处理（分块、解析、索引）
```

**职责**：
- 实现 RAG 全流程
- 多种检索策略融合
- 元数据过滤
- 生成最终答案

#### 2.7.4 重排序器 (`app/rag/rerankers/`)

```
rerankers/
├── __init__.py           # 模块初始化
├── base.py               # 重排序器基类
└── siliconflow_reranker.py # SiliconFlow Reranker 实现
```

**职责**：
- 对初步检索结果进行精排
- 提高结果相关性
- 支持多种 Reranker 模型

#### 2.7.5 向量存储 (`app/rag/vector_stores/`)

```
vector_stores/
├── __init__.py           # 模块初始化
└── vector_store_factory.py # 向量存储工厂（Milvus 集合管理）
```

**职责**：
- 初始化向量数据库
- 管理多个集合（全局食谱、个人食谱、缓存）
- 向量 CRUD 操作

---

### 2.8 业务服务层 (`app/services/`)

```
services/
├── __init__.py                # 模块初始化和导出
├── auth_service.py            # 认证服务（注册、登录、JWT、账户锁定）
├── conversation_service.py    # 对话服务（会话管理、消息处理、流式响应）
├── evaluation_service.py      # RAG 评估服务（RAGAS 框架集成）
├── mcp_service.py             # MCP 服务器管理（注册、鉴权配置）
├── subagent_service.py         # 子代理配置管理（创建、启用、禁用）
├── rag_service.py             # RAG 服务（检索、生成）
├── personal_document_service.py # 个人文档服务（上传、索引）
└── user_service.py            # 用户服务（用户信息管理）
```

**职责**：
- 实现核心业务逻辑
- 协调多个模块协同工作
- 事务管理和错误处理
- 异步任务处理

---

### 2.9 工具集 (`app/tools/`)

```
tools/
├── __init__.py       # 模块初始化
└── web_search.py     # Web 搜索工具（Tavily 集成）
```

**职责**：
- 提供外部工具调用接口
- 扩展 RAG 系统能力
- Web 搜索结果格式化

---

### 2.10 工具函数 (`app/utils/`)

```
utils/
├── structured_json.py # JSON 解析和验证工具
└── image_storage.py   # 图片存储工具（imgbb 上传）
```

**职责**：
- 通用工具函数
- 数据格式化和验证
- 结构化 JSON 处理
- 图片持久化存储（imgbb 集成）

---

### 2.11 应用入口 (`app/main.py`)

**职责**：
- FastAPI 应用初始化
- 中间件配置（CORS、异常处理、安全头、速率限制）
- 路由注册
- 生命周期管理（数据库初始化、缓存清理）

---

### 2.12 安全模块 (`app/security/`)

```
security/
├── __init__.py           # 模块初始化和导出
├── prompt_guard.py       # 基于正则的提示词注入检测
├── sanitizer.py          # 敏感数据过滤和日志脱敏
├── audit.py              # 安全审计日志
├── dependencies.py       # 统一的安全检查辅助函数
├── middleware/           # 中间件
│   ├── __init__.py
│   └── rate_limiter.py   # Redis 速率限制器
└── guardrails/           # NeMo Guardrails 集成
    ├── __init__.py
    ├── guard.py          # Guardrails 封装类
    └── config/           # Guardrails 配置
        ├── config.yml    # 模型配置
        ├── prompts.yml   # 提示词模板
        └── rails/        # 安全规则定义
```

**职责**：
- **prompt_guard.py**：基于正则表达式的快速模式检测，识别常见提示词注入攻击
- **sanitizer.py**：日志敏感数据过滤，防止 API Key、密码等泄露到日志
- **audit.py**：结构化安全审计日志，支持 SIEM 系统对接
- **dependencies.py**：统一的消息安全检查函数，可在多个 endpoint 复用
- **middleware/rate_limiter.py**：基于 Redis 的滑动窗口速率限制
- **guardrails/**：NeMo Guardrails 集成，提供 LLM 驱动的深度安全检测

---

### 2.13 Agent 模块 (`app/agent/`)

```
agent/
├── __init__.py           # 模块初始化（setup_agent_module, setup_mcp_servers）
├── types.py              # 类型定义（AgentChunk, ToolResult, AgentContext 等）
├── context.py            # 上下文构建器和压缩器
├── service.py            # 业务层（AgentService 主入口）
├── agents/               # Agent 实现
│   ├── __init__.py
│   ├── base.py           # Agent 基类（BaseAgent, ReAct 循环实现）
│   └── default.py        # 默认 Agent 实现
├── registry/             # 统一注册中心
│   ├── __init__.py
│   └── hub.py            # AgentHub - 统一管理 Agent、Tool、Provider
├── subagents/             # 子代理系统
│   ├── __init__.py
│   ├── base.py            # 子代理基类（BaseSubagent）
│   ├── registry.py        # 子代理注册中心
│   ├── tool.py            # 子代理 Tool 封装
│   └── builtin/           # 内置子代理
│       ├── __init__.py
│       ├── generic.py     # 通用子代理
│       └── diet_planner.py # 饮食规划专家
├── tools/
│   ├── __init__.py
│   ├── base.py           # Tool 基类（BaseTool, MCPTool, ToolExecutor）
│   ├── common/           # 内置工具
│   │   ├── __init__.py
│   │   ├── calculator.py     # 数学计算工具
│   │   ├── datetime.py       # 日期时间工具
│   │   ├── websearch.py      # Web 搜索工具（Tavily）
│   │   ├── knowledge_base_search.py # 知识库检索工具（RAG）
│   │   └── image_generator.py # 图片生成工具（DALL-E 3 + imgbb）
│   ├── providers/        # 工具提供者
│   │   ├── __init__.py
│   │   ├── local.py      # 本地工具提供者（内置工具）
│   │   ├── mcp.py        # MCP 工具提供者（远程 MCP 服务器）
│   │   └── subagent.py   # 子代理工具提供者
│   └── mcp/              # MCP 协议集成
│       ├── __init__.py
│       ├── client.py     # MCP HTTP 客户端
│       └── setup.py      # MCP 服务器注册
├── database/
│   ├── __init__.py
│   ├── models.py         # ORM 模型（AgentSession, AgentMessage, AgentSubagentConfig）
│   └── repository.py     # 数据访问层（CRUD 操作）
```

**职责**：
- **ReAct 模式执行**：实现 Reasoning + Acting 循环，支持自主推理和工具调用
- **会话管理**：独立的 Agent 会话系统，与 Conversation 模块分离
- **多模态支持**：支持接收和处理图片（最多 4 张，每张最大 10MB），自动上传到 imgbb 持久化
- **用户画像集成**：自动读取用户画像和长期指令，提供个性化服务
- **统一工具系统**：通过 AgentHub 统一管理本地工具和 MCP 远程工具
- **子代理体系**：内置与用户自定义子代理，可作为 Tool 被调用
- **MCP 协议支持**：支持连接远程 MCP 服务器动态加载工具
- **上下文压缩**：自动压缩长对话历史，减少 Token 消耗
- **流式输出**：支持 SSE 事件流，实时反馈工具调用和结果

**核心类**：
- `AgentService`: 业务层入口，处理聊天请求和会话管理
- `BaseAgent`: Agent 基类，实现 ReAct 循环逻辑
- `AgentHub`: 统一注册中心，管理 Agent、Tool 和 Provider
- `BaseSubagent`: 子代理基类（独立 prompt/工具集）
- `SubagentRegistry`: 子代理注册中心
- `BaseTool`: 工具基类，定义工具接口规范
- `MCPTool`: MCP 远程工具封装类
- `ToolExecutor`: 工具执行器，安全执行工具调用
- `LocalToolProvider`: 本地（内置）工具提供者
- `MCPToolProvider`: MCP 远程工具提供者
- `SubagentToolProvider`: 子代理工具提供者
- `MCPClient`: MCP 协议 HTTP 客户端
- `AgentContextBuilder`: 上下文构建器
- `AgentContextCompressor`: 上下文压缩器

**内置工具**：
| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `calculator` | 数学计算 | `expression` (数学表达式) |
| `datetime` | 获取日期时间 | `format`, `timezone` |
| `web_search` | Web 搜索 | `query`, `max_results`, `search_depth` |
| `knowledge_base_search` | 知识库检索 | `query`, `skip_rewrite` |
| `diet_plan` | 饮食计划管理 | `action`, `plan_date`, `meal_type` 等 |
| `diet_log` | 饮食记录管理 | `action`, `log_date`, `items` 等 |
| `diet_analysis` | 饮食分析 | `action`, `target_date`, `week_start_date` 等 |
| `image_generator` | AI 图片生成 | `prompt`, `size`, `quality`, `style` |
| `subagent_<name>` | 子代理工具 | `task`, `background` |

**MCP 集成**：
- 支持 Amap（高德地图）MCP 服务器
- 动态加载远程 MCP 服务器提供的工具
- 工具调用通过 JSON-RPC 协议

**事件类型**（SSE）：
- `session`: 会话信息
- `text`: 文本内容块
- `tool_call`: 工具调用请求
- `tool_result`: 工具执行结果
- `trace`: 执行轨迹（含 `source=subagent` 的子代理输出）
- `done`: 完成信号

---

### 2.14 视觉模块 (`app/vision/`)

```
vision/
├── __init__.py           # 模块初始化
├── agent.py              # 视觉 Agent（图片分析、意图识别）
└── provider.py           # 视觉模型提供商（OpenAI 兼容 API）
```

**职责**：
- 处理用户上传的图片
- 识别菜品、食材等食物相关内容
- 结合文字理解用户完整意图
- 支持多种视觉意图分类（菜品识别、食谱查询、烹饪指导等）

---

### 2.15 饮食管理模块 (`app/diet/`)

```
diet/
├── service.py              # 饮食管理服务（计划、记录、分析）
├── database/
│   ├── models.py           # 饮食数据模型（计划餐次、记录、偏好）
│   └── repository.py       # 数据访问层（CRUD、汇总统计）
├── prompts/
│   ├── log_parsing.py       # AI 饮食记录解析提示词
│   └── __init__.py
└── tools/
    ├── diet_plan_tool.py   # 计划餐次管理 Tool
    ├── diet_log_tool.py    # 饮食记录管理 Tool
    ├── diet_analysis_tool.py # 饮食分析 Tool
    └── __init__.py
```

**职责**：
- 饮食计划（按周/按日）管理，餐次增删改查
- 饮食记录（手动/AI 文本/AI 图片解析）
- 每日/每周营养汇总与计划偏差分析
- 用户饮食偏好、目标信息持久化

---

## 三、前端应用 (`frontend/`)

```
frontend/
├── src/
│   ├── components/       # React 组件
│   │   ├── chat/                # 对话相关组件
│   │   │   ├── ChatMessage.tsx       # 聊天消息组件
│   │   │   ├── ChatInput.tsx         # 输入框组件
│   │   │   ├── ChatWindow.tsx        # 聊天窗口
│   │   │   ├── MessageBubble.tsx     # 消息气泡
│   │   │   ├── MarkdownRenderer.tsx  # Markdown 渲染器
│   │   │   └── ThinkingBlock.tsx     # 思考过程展示
│   │   ├── agent/               # Agent 模式组件
│   │   │   ├── AgentChatInput.tsx    # Agent 输入框
│   │   │   ├── AgentChatWindow.tsx   # Agent 聊天窗口
│   │   │   ├── AgentMessageBubble.tsx # Agent 消息气泡
│   │   │   ├── AgentThinkingBlock.tsx # Agent 思考过程
│   │   │   └── ToolSelector.tsx      # 工具/子代理选择器（动态加载）
│   │   ├── layout/              # 布局组件
│   │   │   ├── Sidebar.tsx           # 侧边栏（支持 Agent 模式切换）
│   │   │   └── UserProfileModal.tsx  # 用户资料与子代理配置弹窗
│   │   ├── common/              # 通用组件
│   │   │   ├── Modal.tsx             # 模态框
│   │   │   ├── ThemeToggle.tsx       # 主题切换
│   │   │   └── CopyButton.tsx        # 复制按钮
│   │   └── KnowledgePanel.tsx   # 知识库面板
│   ├── pages/            # 页面组件
│   │   ├── Login.tsx             # 登录页面
│   │   ├── Register.tsx          # 注册页面
│   │   ├── diet/                  # 饮食管理页面
│   │   │   └── DietManagement.tsx # 周计划 + 记录管理
│   │   ├── Evaluation.tsx        # RAG 评估统计页面
│   │   └── LLMStats.tsx          # LLM 使用统计页面
│   ├── services/         # API 服务
│   │   ├── api/                  # API 模块
│   │   │   ├── client.ts         # Axios 实例配置
│   │   │   ├── auth.ts           # 认证 API
│   │   │   ├── conversation.ts   # 对话 API
│   │   │   ├── agent.ts          # Agent API
│   │   │   ├── diet.ts           # 饮食管理 API
│   │   │   ├── evaluation.ts     # 评估 API
│   │   │   ├── llmStats.ts       # LLM 统计 API
│   │   │   ├── knowledge.ts      # 知识库 API
│   │   │   └── user.ts           # 用户 API
│   │   └── index.ts              # 服务导出
│   ├── contexts/         # React Context
│   │   ├── AuthContext.tsx       # 认证状态管理
│   │   ├── ThemeContext.tsx      # 主题状态管理
│   │   ├── ConversationContext.tsx # 对话状态管理
│   │   └── AgentContext.tsx      # Agent 状态管理
│   ├── hooks/            # 自定义 Hooks
│   │   └── useAuth.tsx           # 认证 Hook
│   ├── types/            # TypeScript 类型定义
│   │   └── index.ts
│   ├── utils/            # 工具函数
│   ├── App.tsx           # 应用根组件（含 Agent 路由）
│   ├── main.tsx          # 应用入口
│   └── index.css         # 全局样式
├── public/               # 静态资源
│   ├── favicon.ico       # 网站图标
│   └── logo.svg          # Logo 文件
├── package.json          # 依赖配置
├── tsconfig.json         # TypeScript 配置
├── vite.config.ts        # Vite 配置
└── tailwind.config.ts    # TailwindCSS 配置
```

**技术栈**：
- React 19 + TypeScript
- Vite（构建工具）
- TailwindCSS（样式）
- React Router（路由）
- Axios（HTTP 客户端）

**路由结构**：
- `/chat` - 标准对话模式
- `/chat/:id` - 指定对话
- `/agent` - Agent 智能模式
- `/agent/:id` - 指定 Agent 会话
- `/diet` - 饮食管理（周计划 + 记录）
- `/agent/diet` - Agent 模式下的饮食管理
- `/knowledge` - 知识库管理
- `/evaluation` - RAG 评估统计
- `/llm-stats` - LLM 使用统计
- `/login` - 登录
- `/register` - 注册

---

## 四、工具脚本 (`scripts/`)

```
scripts/
├── howtocook_loader.py   # HowToCook 数据加载器
├── run_ingestion.py      # 数据摄取主脚本
├── sync_data.py          # 数据同步工具
└── list_categories.py    # 列出菜谱分类
```

**职责**：
- 数据预处理
- 向量化和索引
- 数据库初始化

---

## 五、测试 (`tests/`)

```
tests/
├── __init__.py                  # 测试包初始化
├── test_rag.py                  # RAG 系统测试
├── test_agent.py                # Agent 模块测试
├── test_user_personalization.py # 用户个性化测试
├── test_vision.py               # 视觉模块测试
└── test_guardrails.py           # 安全防护测试
```

**职责**：
- 单元测试
- 集成测试
- 端到端测试
- 安全模块测试
- Agent 功能测试

---

## 六、数据目录 (`data/`)

```
data/
├── HowToCook/            # HowToCook 食谱库（Git Submodule）
│   ├── dishes/           # 菜谱 Markdown 文件
│   ├── tips/             # 烹饪技巧
│   └── README.md
└── debug/                # 调试数据（可选）
    ├── child_chunks.jsonl
    └── parent_documents.jsonl
```

---

## 七、部署配置 (`deployments/`)

```
deployments/
├── docker-compose.yml    # Docker Compose 编排文件
├── init-scripts/         # 数据库初始化脚本
│   └── init.sql
└── volumes/              # 持久化数据卷
    ├── postgres/
    ├── redis/
    ├── milvus/
    ├── minio/
    └── etcd/
```

**职责**：
- 一键启动基础设施
- 数据持久化
- 服务编排

---

## 八、文档目录 (`docs/`)

```
docs/
├── PROJECT_STRUCTURE.md  # 项目结构文档（本文档）
├── README_EN.md          # 英文说明文档
├── SECURITY.md           # 安全策略文档
└── image.png             # 项目 Logo
```

---

## 九、配置文件

### 9.1 `config.yml`

主配置文件，包含：
- LLM 提供商配置（fast/normal 两层模型）
- 数据库连接信息（主机、端口）
- RAG 管道参数（检索、重排序、缓存）
- 缓存策略
- 评估配置
- 视觉模型配置
- Web 搜索配置

### 9.2 `.env`

环境变量文件（不提交到 Git），包含：
- API Keys（LLM、Vision、Reranker、Web Search）
- 数据库密码
- JWT 密钥
- 安全配置

### 9.3 `requirements.txt`

Python 依赖列表，包含所有后端依赖的精确版本号。

---

## 十、数据流示例

### 用户查询流程

1. **用户输入**：前端发送查询请求到 `/api/v1/conversation/query`
2. **API 层**：`conversation.py` 接收请求，验证身份
3. **安全检查**：速率限制、提示词注入检测
4. **服务层**：`conversation_service.py` 处理业务逻辑
5. **意图识别**：`intent.py` 判断查询类型
6. **查询改写**：`query_rewriter.py` 优化查询
7. **缓存查询**：`cache_manager.py` 检查 Redis/Milvus 缓存
8. **检索**：`retrieval.py` 执行混合检索
9. **重排序**：`siliconflow_reranker.py` 精排结果
10. **生成答案**：`generation.py` 调用 LLM 生成回复
11. **LLM 追踪**：`callbacks.py` 记录 Token 使用量
12. **评估**：`evaluation_service.py` 异步评估（可选）
13. **返回结果**：流式或完整返回给前端

### 图片分析流程（多模态）

1. **用户上传**：前端发送图片 + 文字到 `/api/v1/conversation/query`
2. **视觉分析**：`vision/agent.py` 分析图片内容
3. **意图识别**：判断是否与食物相关，分类用户意图
4. **信息提取**：提取菜品名、食材等关键信息
5. **流程衔接**：食物相关则继续 RAG 流程，否则直接响应
6. **结果生成**：结合视觉信息和检索结果生成答案

### RAG 评估流程

1. **响应生成后**：根据采样率决定是否评估
2. **异步提交**：`evaluation_service.py` 后台异步执行
3. **指标计算**：使用 RAGAS 计算 Faithfulness 和 Answer Relevancy
4. **结果存储**：`evaluation_repository.py` 保存到 PostgreSQL
5. **告警检查**：指标低于阈值时触发告警

### 安全检查流程

1. **请求接收**：FastAPI 接收用户请求
2. **速率限制检查**：`rate_limiter.py` 检查 IP/用户请求频率
3. **输入验证**：Pydantic 模型验证消息长度、图片大小等
4. **基础模式检测**：`prompt_guard.py` 正则匹配危险模式
5. **深度安全检测**：`guardrails/guard.py` LLM 驱动的语义分析
6. **业务处理**：通过安全检查后进入正常业务流程
7. **审计记录**：`audit.py` 记录安全事件到结构化日志
8. **敏感数据过滤**：`sanitizer.py` 过滤日志中的敏感信息

### LLM 使用统计流程

1. **请求发起**：`llm/callbacks.py` 创建追踪上下文
2. **Token 计数**：统计输入/输出 Token 数量
3. **时间记录**：记录思考时间、生成时间
4. **成本计算**：基于模型计算请求成本
5. **工具名称提取**：从 Tool Calls 中提取工具名称
6. **持久化**：`llm_usage_repository.py` 保存到 PostgreSQL
7. **统计分析**：前端 `/api/v1/llm-stats/usage` 展示统计结果

### 饮食计划与记录流程

1. **周计划加载**：前端请求 `/api/v1/diet/plans/by-week` 获取一周计划
2. **新增餐次**：`/diet/plans/meals` 添加早餐/午餐/晚餐/加餐
3. **标记已吃**：`/diet/meals/{meal_id}/mark-eaten` 自动生成饮食记录
4. **手动记录**：`/diet/logs` 保存餐次与食物明细
5. **AI 记录**：`/diet/logs/from-text` 解析自然语言或图片
6. **数据汇总**：Repository 汇总热量与宏量营养字段

### 营养分析与偏差流程

1. **每日摘要**：`/diet/analysis/daily` 返回当天营养汇总
2. **每周摘要**：`/diet/analysis/weekly` 聚合全周数据
3. **偏差分析**：`/diet/analysis/deviation` 对比计划与实际
4. **目标偏好**：`/diet/preferences` 读取或更新目标与限制

### Agent 对话流程

1. **用户请求**：前端发送请求到 `/api/v1/agent/chat`（可包含图片）
2. **API 层**：`agent.py` 接收请求，验证身份和图片格式/大小
3. **安全检查**：`dependencies.py` 统一安全检查
4. **会话管理**：`AgentService.chat()` 获取或创建 Session
5. **消息保存**：保存用户消息到数据库
6. **上下文构建**：`AgentContextBuilder` 构建完整上下文
   - 读取用户画像和长期指令
   - 处理图片（如有）：上传到 imgbb 获取持久化 URL
   - 构建包含用户画像、历史消息和图片的完整上下文
7. **Agent 执行**：`BaseAgent.run()` 执行 ReAct 循环
   - 调用 LLM 判断是否需要工具
   - 如需工具，执行 `ToolExecutor.execute()`
   - 如果调用子代理工具，实时输出子代理 trace（`source=subagent`）
   - 收集工具结果，更新消息历史
   - 重复直到生成最终回复
8. **流式输出**：SSE 事件流实时返回
9. **消息保存**：保存 Assistant 消息和执行轨迹
10. **上下文压缩**：后台触发压缩任务（如需要）

### 子代理管理流程

1. **获取列表**：`/api/v1/agent/subagents` 返回内置 + 自定义子代理配置
2. **启用/禁用**：`PATCH /api/v1/agent/subagents/{name}` 更新启用状态
3. **创建自定义**：`POST /api/v1/agent/subagents` 写入配置并同步注册中心
4. **删除自定义**：`DELETE /api/v1/agent/subagents/{name}` 删除并刷新缓存

---

## 十一、扩展指南

### 添加新数据源

1. 在 `scripts/` 下创建新的数据加载器
2. 实现数据解析和向量化逻辑
3. 在 `config.yml` 中添加数据源配置

### 添加新检索策略

1. 在 `app/rag/pipeline/retrieval.py` 中实现新策略
2. 在 `config.yml` 中配置策略参数
3. 在 `rag_service.py` 中集成新策略

### 添加新 Reranker

1. 在 `app/rag/rerankers/` 下创建新文件
2. 继承 `BaseReranker` 基类
3. 在 `rag_config.py` 中添加配置模型
4. 在 `rag_service.py` 中注册新 Reranker

### 添加新安全检测规则

1. 在 `app/security/prompt_guard.py` 中添加正则模式
2. 如需深度检测，在 `app/security/guardrails/config/rails/` 添加新 rail
3. 在 `app/security/audit.py` 中添加事件类型

### 添加自定义 Agent

1. 创建新的 Agent 类继承 `BaseAgent`
2. 在模块初始化时通过 `AgentHub` 注册
3. 配置 `AgentConfig`（名称、描述、系统提示、可用工具）

```python
from app.agent.agents.base import BaseAgent
from app.agent.types import AgentConfig
from app.agent.registry.hub import agent_hub

class CookingAgent(BaseAgent):
    """专门处理烹饪任务的 Agent"""
    pass  # 可覆盖 run() 方法自定义逻辑

# 注册 Agent
agent_hub.register_agent(
    CookingAgent,
    AgentConfig(
        name="cooking_agent",
        description="专门处理烹饪任务的 Agent",
        system_prompt="你是一个烹饪专家...",
        tools=["calculator", "datetime", "web_search"],
        max_iterations=10
    )
)
```

### 添加自定义 Tool

1. 创建新的 Tool 类继承 `BaseTool`
2. 通过 `AgentHub` 注册到本地工具提供者
3. 实现 `execute()` 方法

```python
from app.agent.tools.base import BaseTool
from app.agent.types import ToolResult
from app.agent.registry.hub import agent_hub

class RecipeSearchTool(BaseTool):
    name = "recipe_search"
    description = "搜索食谱数据库"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }

    async def execute(self, query: str, **kwargs) -> ToolResult:
        # 实现搜索逻辑
        results = await search_recipes(query)
        return ToolResult(success=True, data={"recipes": results})

# 注册到本地工具提供者
agent_hub.register_tool(RecipeSearchTool(), provider="local")
```

### 添加 MCP 服务器

1. 在 `config.yml` 中配置 MCP 服务器
2. 在 `.env` 中设置 API Key
3. 在 `app/agent/tools/mcp/setup.py` 中添加注册逻辑

```python
# app/agent/tools/mcp/setup.py
from app.agent.registry.hub import agent_hub

async def setup_my_mcp_server():
    mcp_provider = agent_hub.get_provider("mcp")
    if mcp_provider:
        await mcp_provider.register_server(
            name="my_server",
            endpoint="https://my-mcp-server.com/mcp"
        )
        await mcp_provider.load_server_tools("my_server")
```

---

## 十二、最近更新日志

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v1.10.0 | 2026-01 | 新增子代理体系（内置/自定义）、可视化追踪与管理界面 |
| v1.9.0 | 2026-01 | 新增饮食管理模块（计划/记录/分析）、知识库检索工具、自定义 MCP 服务器管理 |
| v1.8.0 | 2026-01 | Agent 多模态支持（图片上传、imgbb 持久化）、用户画像集成、LLM 配置三层化 |
| v1.7.0 | 2026-01 | 添加 MCP 协议支持、图片生成工具、AgentHub 统一注册、工具提供者架构 |
| v1.6.0 | 2026-01 | 添加 Agent 模块（ReAct 模式、工具系统、会话管理） |
| v1.5.1 | 2026-01 | LLM 模块重构，添加工具名称追踪，优化流式 usage tracking |
| v1.5.0 | 2026-01 | 添加 LLM 使用统计功能 |
| v1.4.0 | 2026-01 | 添加 RAG 评估系统（RAGAS 集成） |
| v1.3.0 | 2025-12 | 添加安全防护体系（Guardrails、速率限制） |
| v1.2.0 | 2025-12 | 添加多模态支持（视觉分析） |
| v1.1.0 | 2025-12 | 添加重排序器、缓存系统 |
| v1.0.0 | 2025-12 | 初始版本 |

---

**此文档将随项目发展持续更新。**
