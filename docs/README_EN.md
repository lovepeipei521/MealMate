<div align="center">
<img src="./image.png" alt="CookHero Logo" width="512" />

**Intelligent Cooking & Diet Management Assistant · Your Personalized Diet Hero**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.122-009688.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-1.1-green.svg)](https://www.langchain.com/)
[![Milvus](https://img.shields.io/badge/Milvus-2.6-orange.svg)](https://milvus.io/)
[![NeMo Guardrails](https://img.shields.io/badge/NeMo%20Guardrails-0.12-76B900.svg)](https://github.com/NVIDIA/NeMo-Guardrails)
[![RAGAS](https://img.shields.io/badge/RAGAS-0.2-purple.svg)](https://docs.ragas.io/)
[![License](https://img.shields.io/badge/License-APACHE%202.0-blue.svg)](LICENSE)

[简体中文](README.md) | English

<div align="center">
<p align="center">
  <img src="./docs/agent.jpg" width="48%">
  <img src="./docs/demo_2x.gif" width="48%"/>
  <img src="./docs/diet.jpg" width="48%">
  <img src="./docs/statistics.jpg" width="48%">
</p>
</div>


---

## 📖 Project Overview

**CookHero** is a personalized diet management platform powered by LLM, RAG, Agents, multimodal models, and nutrition analytics. It is more than a recipe library—it is your “diet hero assistant” that helps you plan, log, analyze, and improve daily eating habits end-to-end.

- 🔍 **Smart Q&A**: Answer cooking techniques, ingredient pairings, and nutrition questions
- 🍽️ **Personalized Recommendations**: Suggest dishes aligned with goals and dietary restrictions
- 🗓️ **Meal Planning**: Weekly meal planning for breakfast/lunch/dinner/snacks
- 🧾 **AI Logging**: One-click text/image logging with estimated nutrition
- 📊 **Nutrition Analytics**: Daily/weekly summaries with plan vs actual deviation insights
- 🧠 **Deep Understanding**: Multi-turn conversations for precise action suggestions
- 🌐 **Real-time Search**: Integrate web search for the latest cooking trends

CookHero is built for kitchen beginners, fitness/weight-loss users, glycemic control scenarios, allergy-sensitive users, and family kitchens—making cooking more professional, intelligent, and sustainable.

> The internal recipe library is sourced from [Anduin2017/HowToCook](https://github.com/Anduin2017/HowToCook), thanks to the contributors of that project!

---

## ⚡ Technical Highlights

- **LLM + RAG Hybrid Retrieval**: Vector + BM25 + reranker with multi-level caching
- **Agent ToolHub**: ReAct reasoning with tool calls and MCP extensibility
- **Subagent Expert System**: Built-in + user-defined subagents, enabled on demand
- **Multimodal Parsing**: Image understanding for cooking and diet logging
- **Quality & Observability**: RAGAS evaluation + LLM usage analytics dashboards
- **Security by Design**: Prompt injection guardrails, rate limiting, audit logs
- **Modern Full Stack**: FastAPI + React + PostgreSQL + Milvus + Redis + MinIO

## ✨ Core Features

### 1. Agent Intelligent Mode
- **ReAct Pattern**: Implements reasoning + action loop for autonomous decision-making and tool invocation
- **Multimodal Support**: Upload images (up to 4, max 10MB each), automatically persisted to imgbb storage
- **User Profile Integration**: Automatically reads user profile and long-term instructions for personalized service
- **Subagents**: Built-in/custom specialists callable as tools with their own prompts and toolsets
- **Subagent Management**: Create/enable/disable in profile; Agents panel in Tool Selector
- **Built-in Tools**:
  - Diet Tools: meal planning, diet logging, nutrition analysis
  - Knowledge Base Search: Call the internal RAG retriever with sources
  - Web Search: Integrated Tavily search engine for real-time information queries
  - AI Image Generation: Generate images using DALL-E 3 etc., auto-upload to imgbb for persistence
  - Calculator: Mathematical calculations
  - DateTime: Get current time, timezone conversion
- **MCP Protocol Support**: Allow users to register MCP servers with auth headers
- **Extensible Architecture**: Unified management of Agents, Tools, and Providers via AgentHub
- **Context Compression**: Automatically compress long conversation history to reduce Token consumption
- **Real-time Feedback**: SSE event stream for live display of tool calls and results
- **Execution Tracing**: Layered traces for Agent and Subagent output
- **Tool Selection**: Frontend can dynamically select tools and subagents

### 2. Meal Planning & Logging
- Weekly planning for breakfast/lunch/dinner/snacks
- Planned meals automatically summarize calories and macros
- One-click "mark as eaten" converts plan to log entries
- AI parses text/image diet descriptions with estimated nutrition
- Support for updating, copying, and annotating meals

### 3. Nutrition Analytics & Goal Tracking
- Daily/weekly nutrition summaries (calories, protein, fat, carbs)
- Plan vs actual deviation analysis to surface habit drift
- Goal management for calorie/protein/fat/carb targets
- Data source tracking: manual, AI text, AI image

### 4. Intelligent Conversational Queries
- Natural language understanding of user needs (e.g., "I want to make a low-fat, high-protein dinner")
- Multi-turn conversation support with context history
- Automatic intent recognition (query, recommendation, chat, etc.)
- Streaming responses with real-time display

### 5. Hybrid Retrieval & Reranking
- **Vector Retrieval**: Semantic similarity matching (based on Milvus)
- **BM25 Retrieval**: Keyword exact matching
- **Metadata Filtering**: Filter by cooking time, difficulty, nutrition, etc.
- **Smart Reranking**: Use Reranker models (e.g., Qwen3-Reranker) for secondary precision ranking
- **Multi-level Caching**: Redis + Milvus dual-layer caching for improved response speed

### 6. Personalized Profiles & Knowledge Base
- Users can upload personal recipes, automatically analyzed and indexed
- Global recipe library (from [HowToCook](https://github.com/Anduin2017/HowToCook)) merged with personal recipes
- Intelligent parsing of Markdown format recipes
- Persistent diet preferences, allergies, and health goals
- Customizable model response style
- Support for OpenAI-compatible custom model integration

### 7. Multimodal Support
- **Image Recognition**: Upload food/ingredient/diet images for intelligent identification
- **Intent Understanding**: Combine images and text to understand complete user intent
- **Multiple Scenarios**: Dish identification, ingredient recognition, cooking guidance, diet logging, recipe queries
- **Flexible Integration**: Support for OpenAI-compatible vision model APIs
- **Image Limits**: Up to 4 images, 10MB per image (Agent/diet logging)

### 8. RAG Evaluation System
- **Quality Monitoring**: Automated evaluation based on the RAGAS framework
- **Core Metrics**: Faithfulness, Answer Relevancy
- **Async Evaluation**: Background asynchronous execution without affecting response speed
- **Trend Analysis**: Support for evaluation trend viewing and quality alerts
- **Data Persistence**: Evaluation results stored in PostgreSQL

### 9. LLM Usage Statistics
- **Real-time Monitoring**: Track Token usage for each request
- **Performance Metrics**: Record response time, thinking time, generation time
- **Statistical Analysis**: Usage statistics by user, session, and module
- **Tool Tracking**: Record Agent tool call names
- **Visualization**: Frontend LLM statistics page

### 10. Security Protection System
- **Multi-layer Defense**: Input validation → Pattern detection → LLM deep detection
- **Prompt Injection Protection**: Dual detection mechanism based on rules and AI
- **Rate Limiting**: Redis sliding window algorithm with endpoint-specific limits
- **Account Security**: Login failure lockout, JWT expiration policy, security headers
- **Sensitive Data Protection**: Log sanitization, API key filtering
- **Security Audit**: Structured JSON audit logs, SIEM system integration support

> 📖 For detailed security architecture, see [Security Documentation](SECURITY.md)

---

## 🚀 Quick Start

### Prerequisites

- **Python**: >= 3.12
- **Node.js**: >= 18
- **Docker** and **Docker Compose** (recommended)

### Method 1: Docker One-Click Deployment (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/Decade-qiu/CookHero.git
   cd CookHero
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file and fill in necessary API Keys
   ```

3. **Start infrastructure**
   ```bash
   cd deployments
   docker-compose up -d
   ```
   This will start:
   - PostgreSQL (port 5432)
   - Redis (port 6379)
   - Milvus (port 19530)
   - MinIO (port 9001)
   - Etcd (internal use)

4. **Install Python dependencies and start backend**
   ```bash
   cd ..
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt

   # Initialize database
   python -m scripts.howtocook_loader

   # Start backend service
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Start frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. **Access the application**
   - Frontend: http://localhost:5173
   - Diet Management: http://localhost:5173/diet
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

---

## ⚙️ Configuration

### 1. Environment Variables (`.env`)

Create a `.env` file (refer to `.env.example`):

```env
# ==================== LLM API Configuration ====================
# Main API Key (default for all modules)
LLM_API_KEY=your_main_api_key

# Fast Model API Key (for intent detection, query rewriting)
FAST_LLM_API_KEY=your_fast_model_api_key

# Vision Model API Key (for multimodal analysis)
VISION_API_KEY=your_vision_model_api_key

# Reranker API Key (for result reranking)
RERANKER_API_KEY=your_reranker_api_key

# ==================== Database Configuration ====================
DATABASE_PASSWORD=your_postgres_password

# Redis Password (optional)
REDIS_PASSWORD=your_redis_password

# Milvus Authentication (optional)
MILVUS_USER=root
MILVUS_PASSWORD=your_milvus_password

# ==================== Web Search ====================
WEB_SEARCH_API_KEY=your_tavily_api_key

# ==================== MCP Integration ====================
# Amap (Gaode Maps) MCP Service API Key
AMAP_API_KEY=your_amap_api_key

# ==================== Image Generation ====================
# OpenAI-compatible image generation API Key (DALL-E 3, etc.)
IMAGE_GENERATION_API_KEY=your_openai_api_key
# imgbb image hosting API Key (for image persistence)
IMGBB_STORAGE_API_KEY=your_imgbb_api_key

# ==================== Security / Authentication ====================
JWT_SECRET_KEY=your_secure_jwt_secret_key
JWT_ALGORITHM=HS256

# Access token expiration (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Refresh token expiration (days)
REFRESH_TOKEN_EXPIRE_DAYS=7

# ==================== Rate Limiting ====================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_LOGIN_PER_MINUTE=5
RATE_LIMIT_CONVERSATION_PER_MINUTE=30
RATE_LIMIT_GLOBAL_PER_MINUTE=100

# ==================== Account Security ====================
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
MAX_MESSAGE_LENGTH=10000
MAX_IMAGE_SIZE_MB=5
PROMPT_GUARD_ENABLED=true
```

### 2. Main Configuration File (`config.yml`)

`config.yml` contains the core configuration of the application:

```yaml
# LLM Provider Configuration (Layered: fast / normal / vision)
llm:
  fast:    # Fast models (low latency)
  normal:  # Standard models (high quality)
  vision:  # Vision models (multimodal)

# Data paths
paths:
  base_data_path: "data/HowToCook"

# Embedding model
embedding:
  model_name: "BAAI/bge-small-zh-v1.5"

# Vector store
vector_store:
  type: "milvus"
  collection_names:
    recipes: "cook_hero_recipes"
    personal: "cook_hero_personal_docs"

# Retrieval configuration
retrieval:
  top_k: 9
  score_threshold: 0.2
  ranker_type: "weighted"
  ranker_weights: [0.8, 0.2]

# Reranker configuration
reranker:
  enabled: true
  model_name: "Qwen/Qwen3-Reranker-8B"

# Cache configuration
cache:
  enabled: true
  ttl: 3600
  l2_enabled: true
  similarity_threshold: 0.92

# Web search configuration
web_search:
  enabled: true
  max_results: 6

# Vision/Multimodal configuration
vision:
  model:
    enabled: true
    model_name: "Qwen/QVQ-72B-Preview"

# Evaluation configuration
evaluation:
  enabled: true
  async_mode: true
  sample_rate: 1.0

# MCP configuration
mcp:
  amap:
    enabled: true

# Image generation configuration
image_generation:
  enabled: true
  model: "dall-e-3"

# Image storage configuration (imgbb)
image_storage:
  enabled: true

# Database connections
database:
  postgres:
    host: "localhost"
    port: 5432
  redis:
    host: "localhost"
    port: 6379
  milvus:
    host: "localhost"
    port: 19530
```

See comments in `config.yml` for detailed explanations.

---

## 🗺️ Roadmap

- [x] **Multimodal Support**: Ingredient image recognition, dish identification ✅
- [x] **RAG Evaluation System**: Quality monitoring based on RAGAS ✅
- [x] **Security Protection System**: Input validation, prompt injection protection, rate limiting ✅
- [x] **LLM Usage Statistics**: Token monitoring, performance analysis page ✅
- [x] **Agent Intelligent Mode**: ReAct reasoning, tool invocation, session management ✅
- [x] **Subagent Expert System**: Built-in/custom subagents with visual traces ✅
- [x] **MCP Protocol Support**: Remote tool loading, Amap integration ✅
- [x] **AI Image Generation**: DALL-E 3 integration, imgbb persistent storage ✅
- [x] **Diet Planning & Logging**: Weekly plans, mark-as-eaten, AI logging ✅
- [x] **Nutrition Analytics & Goals**: Daily/weekly summaries, deviation analysis ✅
- [ ] **Voice Interaction**: Voice input queries, voice step narration
- [ ] **Community Features**: User sharing, ratings, comments
- [ ] **Smart Ingredient Management**: Fridge inventory, expiration reminders
- [ ] **AR Cooking Guidance**: Augmented reality cooking assistance
- [ ] **More Agent Tools**: Recipe search, nutrition calculation, shopping list generation

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the [APACHE LICENSE 2.0](LICENSE). See the LICENSE file for details.

---

## 🙏 Acknowledgments

- [HowToCook](https://github.com/Anduin2017/HowToCook) - Quality open-source recipe library
- [LangChain](https://www.langchain.com/) - Powerful LLM application framework
- [Milvus](https://milvus.io/) - High-performance vector database
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [NVIDIA NeMo Guardrails](https://developer.nvidia.com/nvidia-nemo) - Advanced security protection framework
- [RAGAS](https://docs.ragas.io/) - RAG evaluation framework

---

<div align="center">

**If this project helps you, please give it a ⭐️ Star!**

</div>
