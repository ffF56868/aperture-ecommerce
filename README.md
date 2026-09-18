# Aperture — 电商店铺模板

一个生产级、作品集品质的全栈电商模板：后端为 Django 5 / DRF，提供基于 OTP 的认证和模拟支付流程；前端为 React 19 / TypeScript，采用暗黑、精密仪器般的视觉风格。端到端构建，每一层都经过真实工具运行验证——不只是写了出来，而是完成了编译、Lint、数据库迁移，并通过真实的 HTTP 请求跑通全流程。

## 架构总览

```
root/
├── backend/     Django 5 + DRF — REST API、JWT 认证、Celery worker
├── frontend/    React 19 + Vite + TypeScript — SPA，暗黑高级感设计体系
├── docker-compose.yml
└── .github/workflows/ci.yml
```

后端提供带版本前缀的 REST API（`/api/v1/`），并用 drf-spectacular 生成文档（Swagger UI + ReDoc）。前端是纯客户端渲染的 SPA，通过 HTTP 与后端通信，自有游客购物车状态，登录后自动合并到后端购物车。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.13, Django 5, DRF, Celery + Redis, PostgreSQL + pgvector, MinIO（兼容 S3）, drf-spectacular, django-filter |
| 后端工具 | pytest-django, factory-boy 模式 fixture, Ruff, Black, isort |
| 前端 | React 19, Vite, TypeScript（严格模式）, Tailwind CSS, Framer Motion, React Router v7, TanStack Query v5, Zustand, Axios |
| 前端工具 | Vitest, React Testing Library, ESLint（flat config）, Prettier |
| 基础设施 | Docker Compose, 多阶段 Dockerfile, Nginx（前端）, GitHub Actions CI |

## 设计体系

前端遵循**暗黑、精密仪器般的视觉风格**——核心视觉意象是相机光圈：一切都会"咔哒"一声对焦清晰。标志性细节：

- **取景框式悬停状态** — 商品卡和分类卡悬停时会"咔"地弹出取景器四角括号（`src/styles/index.css` 中的 `.bracket-frame`），把光学隐喻贯穿到每个可交互界面。
- **字体体系** — Space Grotesk（标题）、Inter（正文）、JetBrains Mono（价格、SKU、时间戳）——所有数字全程获得一种"规格表"式的技术感处理。
- **颜色令牌** — 近黑底色（`#09090C`），搭配靛蓝/紫罗兰主强调色与暖珊瑚次要色，全部在 `tailwind.config.js` 中统一定义、全站使用（组件里不出现临时十六进制色值）。
- **动效** — 用 Framer Motion 实现页面载入揭示和 Toast 过渡；所有动画都尊重 `prefers-reduced-motion` 设置。

## 交付前已验证

以下每一条都是本次构建中实际运行过的，不只是写写而已：

**后端**
- `python manage.py check` → 0 个问题；`makemigrations --check` → 无迁移漂移。
- `migrate` 干净应用（构建沙箱中以 SQLite 代替 Postgres）。
- `ruff check .`、`black --check .`、`isort --check-only .` → 全部通过。
- `python manage.py spectacular` → OpenAPI schema 生成，**零警告**。
- **23 个 pytest 测试全部通过**，覆盖：注册 + OTP 缓存、正确/错误 OTP 校验、登录成功/失败路径（未验证用户、密码错误）、修改用户名与密码、商品列表/筛选/搜索、分类列表、购物车加购/数量合并/需登录/清空、结算（创建订单、扣减库存、空购物车拒绝、库存不足拒绝），以及 initiate → verify 支付流程将订单状态翻转为 `PAID`。
- 通过 Django 测试客户端跑了一整套手动端到端模拟（注册 → 验证 → 登录 → 浏览 → 购物车 → 结算 → 支付 → 改密码 → 联系表单 → 登出），针对真实 SQLite 数据库发起真实 HTTP 风格请求并断言。

**前端**
- `npm install` 干净完成。
- `npx tsc -b` → 严格模式下 **0 个 TypeScript 错误**。
- `npm run build` → 生产构建干净，vendor 分包（react/query/motion 拆出），无包体积警告。
- `npx eslint .` → 0 个错误。
- **10 个 Vitest 测试全部通过**，包含一个集成测试：通过 `MemoryRouter` + `QueryClientProvider` 挂载真实的 `<App />`，渲染 Home、404、Login、Register 路由——能捕获仅靠类型检查漏掉的运行时错误。
- `vite preview` 成功提供服务端构建产物并返回 HTTP 200。
- `docker-compose.yml` 解析为有效 YAML，包含全部 7 个服务（`db`、`redis`、`minio`、`backend`、`celery_worker`、`celery_beat`、`frontend`）。

## 一键启动整个技术栈

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# 编辑 backend/.env — 至少要把 DJANGO_SECRET_KEY 换成真实值

docker compose up --build
```

- 前端：`http://localhost:3000/`
- API 根路径：`http://localhost:8000/api/v1/`
- Swagger UI：`http://localhost:8000/api/docs/`
- ReDoc：`http://localhost:8000/api/redoc/`
- Django 管理后台：`http://localhost:8000/admin/`
- MinIO 控制台：`http://localhost:9001/`

后端容器启动后，创建一个管理员账号：

```bash
docker compose exec backend python manage.py createsuperuser
```

### 售后 Agent 知识库（RAG）

售后 Agent 对尺码、面料、洗护和非实时规则使用可引用的中文知识库；订单、退款和发货仍使用受控业务工具。配置 `OPENAI_API_KEY` 后初始化向量：

```bash
docker compose exec backend python manage.py seed_after_sales_knowledge
```

如需校验并修复 PostgreSQL 与 Milvus 的索引一致性：

```powershell
docker compose exec backend python manage.py repair_after_sales_knowledge
```

详细的职责边界、维护和验收步骤见 [售后 Agent 知识库说明](docs/after-sales-rag.md)。

### 售后 Agent Eval

项目内置 20 条确定性回放评测，覆盖订单归属、人工确认、RAG 引用、提示注入、危险工具、schema 约束、连续失败和工具循环上限。运行评测不会消耗 OpenAI 额度，临时数据会在事务结束时自动回滚：

```bash
docker compose exec backend python manage.py run_after_sales_agent_eval
```

详细的评测设计、指标与报告说明见 [售后 Agent Eval 说明](docs/after-sales-agent-eval.md)。

管理员也可以登录网站后打开“Agent 评测”，点击“运行评测”查看历史批次、指标卡、简单进度图和 20 条案例明细；还可以进入“RAG 知识库”上传 `.txt`、`.md`、Word、PDF 或网页 URL，按商品/分类绑定规则并查看 Milvus 索引状态。

## 手动（非 Docker）安装

**后端**
```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # 把 POSTGRES_HOST/REDIS_URL 指向 localhost
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**前端**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev   # 运行在 http://localhost:5173，/api 代理到 :8000
```

**Celery**（用于 OTP 发送 / 联系表单通知 / 后台清理）
```bash
cd backend
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info   # 用于定时清理任务
```

## 环境变量

完整参考见 `backend/.env.example` 和 `frontend/.env.example`。关键的几个：

| 变量 | 位置 | 用途 |
|---|---|---|
| `DJANGO_SECRET_KEY` | 后端 | 必填 — 除本地开发外务必生成真实值 |
| `POSTGRES_*` | 后端 | 数据库连接 |
| `REDIS_URL` / `CELERY_BROKER_URL` | 后端 | 缓存 + 任务队列 |
| `USE_S3` / `AWS_*` | 后端 | 切换 MinIO/S3 媒体存储 |
| `VITE_API_BASE_URL` | 前端 | API 基础路径（默认 `/api/v1`，开发时走代理） |

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/categories/` | 列出启用中的分类 |
| GET | `/api/v1/categories/{slug}/` | 分类详情 |
| GET | `/api/v1/products/` | 商品列表（`?category=`、`?popular=`、`?min_price=`、`?max_price=`、`?in_stock=`、`?ordering=`、`?search=`） |
| GET | `/api/v1/products/{slug}/` | 商品详情 |
| POST | `/api/v1/auth/register/` | 第 1 步：用户名 + 手机号 + 密码 → 发送 OTP |
| POST | `/api/v1/auth/verify-otp/` | 第 2 步：校验验证码，解锁账号 |
| POST | `/api/v1/auth/login/` | 用户名 + 密码 → JWT access/refresh |
| POST | `/api/v1/auth/logout/` | 将 refresh token 加入黑名单 |
| POST | `/api/v1/auth/token/refresh/` | 轮换 access token |
| GET | `/api/v1/profile/` | 当前用户资料 |
| PATCH | `/api/v1/profile/change-username/` | 修改用户名 |
| POST | `/api/v1/profile/change-password/` | 修改密码 |
| GET | `/api/v1/cart/` | 查看购物车 |
| POST | `/api/v1/cart/add/` | 加入购物车 |
| PATCH | `/api/v1/cart/items/{id}/` | 更新商品数量 |
| DELETE | `/api/v1/cart/items/{id}/remove/` | 移除单个商品 |
| DELETE | `/api/v1/cart/clear/` | 清空购物车 |
| GET | `/api/v1/orders/` | 订单历史 |
| POST | `/api/v1/orders/checkout/` | 从购物车创建订单 |
| POST | `/api/v1/payments/initiate/` | 发起模拟支付 |
| POST | `/api/v1/payments/verify/` | 支付网关回调/webhook |
| POST | `/api/v1/contact/` | 提交联系咨询 |

完整的请求/响应 schema 与示例见 Swagger UI。

## 测试

```bash
# 后端
cd backend
pytest                    # 23 个测试：认证/OTP、商品、购物车/结算/支付
ruff check . && black --check . && isort --check-only .

# 前端
cd frontend
npm run test               # 10 个测试：UI 基础组件、工具函数、整应用挂载冒烟测试
npm run lint
npm run build               # 同时做类型检查（tsc -b && vite build）
```

## CI/CD

`.github/workflows/ci.yml` 在每次 push/PR 到 `main` 时运行：

1. **backend** — Ruff、Black、isort、`manage.py check`、迁移漂移检查、pytest
   （针对真实的 Postgres + Redis 服务容器运行）。
2. **frontend** — ESLint、`tsc -b` + `vite build`、Vitest。
3. **docker-build** — 构建两个 Docker 镜像（依赖第 1、2 步通过），在合并前捕获
   Dockerfile 回归。

部署时，把同一套 Dockerfile 指向托管的 Postgres/Redis/S3（例如 RDS +
ElastiCache + S3，或单机 Docker Compose 部署配合托管 Postgres 附加服务），
设置 `DJANGO_SETTINGS_MODULE=config.settings.production`，并通过同一个 Nginx
容器或 CDN 提供前端静态 `dist/` 产物。

## 许可证

MIT — 见 `LICENSE`。可自由用作你自己项目的起点。

