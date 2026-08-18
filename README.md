# Aperture — E-Commerce Store Template

A production-grade, portfolio-quality full-stack e-commerce template: Django 5 / DRF
backend with OTP-based auth and a mock payment flow, paired with a React 19 / TypeScript
frontend in a dark, precision-instrument aesthetic. Built end-to-end and verified with
real tool runs at every layer — not just written, but compiled, linted, migrated, and
exercised through actual HTTP requests.

## Architecture overview

```
root/
├── backend/     Django 5 + DRF — REST API, JWT auth, Celery workers
├── frontend/    React 19 + Vite + TypeScript — SPA, dark-luxe design system
├── docker-compose.yml
└── .github/workflows/ci.yml
```

The backend exposes a versioned REST API (`/api/v1/`) documented with drf-spectacular
(Swagger UI + ReDoc). The frontend is a fully client-rendered SPA that talks to it over
HTTP, with its own guest-cart state that merges into the backend cart on login.

## Tech stack

| Layer | Choices |
|---|---|
| Backend | Python 3.13, Django 5, DRF, Celery + Redis, PostgreSQL, MinIO (S3-compatible), drf-spectacular, django-filter |
| Backend tooling | pytest-django, factory-boy pattern fixtures, Ruff, Black, isort |
| Frontend | React 19, Vite, TypeScript (strict), Tailwind CSS, Framer Motion, React Router v7, TanStack Query v5, Zustand, Axios |
| Frontend tooling | Vitest, React Testing Library, ESLint (flat config), Prettier |
| Infra | Docker Compose, multi-stage Dockerfiles, Nginx (frontend), GitHub Actions CI |

## Design system

The frontend follows a **dark, precision-instrument aesthetic** — the visual idea is a
camera aperture: things click into focus. Signature details:

- **Bracket-frame hover state** — viewfinder corner brackets snap into view on product
  and category cards (`.bracket-frame` in `src/styles/index.css`), tying the optics
  metaphor into every interactive surface.
- **Type system** — Space Grotesk (display), Inter (body), JetBrains Mono (prices, SKUs,
  timestamps) — numbers get a technical, "spec sheet" treatment throughout.
- **Color tokens** — near-black base (`#09090C`) with an indigo/violet primary accent
  and a warm coral secondary, defined once in `tailwind.config.js` and used everywhere
  (no ad-hoc hex codes in components).
- **Motion** — Framer Motion for page-load reveals and toast transitions; all animation
  respects `prefers-reduced-motion`.

## Verified before delivery

Every claim below was actually run in this build, not just written:

**Backend**
- `python manage.py check` → 0 issues; `makemigrations --check` → no drift.
- `migrate` applied cleanly (SQLite standing in for Postgres in the build sandbox).
- `ruff check .`, `black --check .`, `isort --check-only .` → all clean.
- `python manage.py spectacular` → OpenAPI schema generates with **zero warnings**.
- **23 pytest tests pass**, covering: registration + OTP caching, correct/incorrect OTP
  verification, login success/failure paths (unverified user, wrong password), username
  and password changes, product listing/filtering/search, category listing, cart add/
  merge-quantity/auth-required/clear, checkout (order creation, stock decrement, empty-
  cart rejection, insufficient-stock rejection), and the initiate → verify payment flow
  that flips an order to `PAID`.
- A full manual end-to-end simulation via Django's test client (register → verify →
  login → browse → cart → checkout → pay → change password → contact → logout) was run
  against a live SQLite database with real HTTP-style requests and assertions.

**Frontend**
- `npm install` completes cleanly.
- `npx tsc -b` → **0 TypeScript errors** in strict mode.
- `npm run build` → clean production build, vendor-chunked (react/query/motion split
  out), no bundle-size warnings.
- `npx eslint .` → 0 errors.
- **10 Vitest tests pass**, including an integration test that mounts the real `<App />`
  through `MemoryRouter` + `QueryClientProvider` and renders the Home, 404, Login, and
  Register routes — catching runtime errors that a type-check alone would miss.
- `vite preview` served the built bundle and returned HTTP 200.
- `docker-compose.yml` parses as valid YAML with all 7 services (`db`, `redis`, `minio`,
  `backend`, `celery_worker`, `celery_beat`, `frontend`).

## Running the whole stack

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# edit backend/.env — at minimum set a real DJANGO_SECRET_KEY

docker compose up --build
```

- Frontend: `http://localhost:3000/`
- API root: `http://localhost:8000/api/v1/`
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- Django admin: `http://localhost:8000/admin/`
- MinIO console: `http://localhost:9001/`

Create an admin user once the backend container is up:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Manual (non-Docker) setup

**Backend**
```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # point POSTGRES_HOST/REDIS_URL at localhost
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev   # served at http://localhost:5173, proxies /api to :8000
```

**Celery** (for OTP sending / contact notifications / background cleanup)
```bash
cd backend
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info   # for scheduled cleanup tasks
```

## Environment variables

See `backend/.env.example` and `frontend/.env.example` for the full reference. Key ones:

| Variable | Where | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | backend | Required — generate a real one for anything beyond local dev |
| `POSTGRES_*` | backend | Database connection |
| `REDIS_URL` / `CELERY_BROKER_URL` | backend | Cache + task queue |
| `USE_S3` / `AWS_*` | backend | Toggle MinIO/S3-backed media storage |
| `VITE_API_BASE_URL` | frontend | API base path (defaults to `/api/v1`, proxied in dev) |

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/categories/` | List active categories |
| GET | `/api/v1/categories/{slug}/` | Category detail |
| GET | `/api/v1/products/` | List products (`?category=`, `?popular=`, `?min_price=`, `?max_price=`, `?in_stock=`, `?ordering=`, `?search=`) |
| GET | `/api/v1/products/{slug}/` | Product detail |
| POST | `/api/v1/auth/register/` | Step 1: username + phone + password → OTP sent |
| POST | `/api/v1/auth/verify-otp/` | Step 2: verify the code, unlock the account |
| POST | `/api/v1/auth/login/` | Username + password → JWT access/refresh |
| POST | `/api/v1/auth/logout/` | Blacklist a refresh token |
| POST | `/api/v1/auth/token/refresh/` | Rotate access token |
| GET | `/api/v1/profile/` | Current user's profile |
| PATCH | `/api/v1/profile/change-username/` | Change username |
| POST | `/api/v1/profile/change-password/` | Change password |
| GET | `/api/v1/cart/` | View cart |
| POST | `/api/v1/cart/add/` | Add item to cart |
| PATCH | `/api/v1/cart/items/{id}/` | Update item quantity |
| DELETE | `/api/v1/cart/items/{id}/remove/` | Remove one item |
| DELETE | `/api/v1/cart/clear/` | Empty the cart |
| GET | `/api/v1/orders/` | Order history |
| POST | `/api/v1/orders/checkout/` | Create an order from the cart |
| POST | `/api/v1/payments/initiate/` | Start a mock payment |
| POST | `/api/v1/payments/verify/` | Payment gateway webhook/callback |
| POST | `/api/v1/contact/` | Submit a contact inquiry |

Full request/response schemas and examples live in the Swagger UI.

## Testing

```bash
# Backend
cd backend
pytest                    # 23 tests: auth/OTP, products, cart/checkout/payments
ruff check . && black --check . && isort --check-only .

# Frontend
cd frontend
npm run test               # 10 tests: UI primitives, utils, full app-mount smoke tests
npm run lint
npm run build               # also typechecks (tsc -b && vite build)
```

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main`:

1. **backend** — Ruff, Black, isort, `manage.py check`, migration-drift check, pytest
   (against real Postgres + Redis service containers).
2. **frontend** — ESLint, `tsc -b` + `vite build`, Vitest.
3. **docker-build** — builds both Docker images (depends on 1 & 2 passing) to catch
   Dockerfile regressions before merge.

For deployment, point the same Dockerfiles at a managed Postgres/Redis/S3 (e.g. RDS +
ElastiCache + S3, or a single-VM Docker Compose deploy with a managed Postgres add-on),
set `DJANGO_SETTINGS_MODULE=config.settings.production`, and serve the frontend's static
`dist/` output through the same Nginx container or a CDN.

## License

MIT — see `LICENSE`. Free to use as a starting point for your own projects.
