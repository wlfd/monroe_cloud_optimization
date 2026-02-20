# Phase 1: Foundation - Research

**Researched:** 2026-02-20
**Domain:** FastAPI + PostgreSQL + JWT auth + React + shadcn/ui + Azure Container Apps
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- App shell + routing — not just a login page; Phase 3+ features slot into a structure that already exists
- Sidebar nav + top bar layout: fixed left sidebar with nav links (Dashboard, Anomalies, Recommendations, Attribution, Settings) and a top bar with user info and logout
- After successful login, user lands at /dashboard showing a clear placeholder ("Dashboard coming in Phase 3") — establishes the route and layout without premature content
- Desktop-first — not optimizing for mobile in Phase 1; can be addressed later

### Claude's Discretion
- Token storage strategy (HttpOnly cookies vs localStorage) — choose what's most secure and clean given FastAPI + React setup
- First admin bootstrap approach (seed script, env var, or /setup endpoint) — whatever is simplest for a solo developer first-run experience
- Health check depth (/health endpoint contents — app-only vs DB/Redis ping)
- Login page polish and form UX details (validation feedback, password visibility toggle, etc.)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | User can log in with email and password and receive a JWT access token | PyJWT + pwdlib[argon2], FastAPI OAuth2PasswordBearer pattern, POST /auth/login endpoint |
| AUTH-02 | User session persists via 7-day refresh token across browser restarts | HttpOnly cookie storage for refresh token, user_sessions table with token_hash, 7-day expiry |
| AUTH-03 | User can log out and invalidate their current session | Revoke refresh token in user_sessions (set revoked=true), POST /auth/logout pattern |
| API-02 | API requires JWT bearer token authentication | FastAPI Depends(get_current_user) dependency, OAuth2PasswordBearer scheme |
| API-03 | OpenAPI documentation auto-generated and accessible at /api/docs | FastAPI built-in: docs_url="/api/docs", redoc_url="/api/redoc" |
</phase_requirements>

---

## Summary

Phase 1 builds the deployable skeleton that all future phases slot into. The technical domain covers five distinct concerns: (1) FastAPI project structure with async SQLAlchemy 2.0 + PostgreSQL, (2) JWT authentication with access + refresh tokens, (3) OpenAPI docs accessible at /api/docs, (4) a React + shadcn/ui shell with authenticated layout and routing, and (5) Azure Container Apps deployment with health checks. The architecture is thoroughly pre-specified in ARCHITECTURE.md, so research focus was on current library choices, changed best practices, and implementation pitfalls.

The most significant finding is that two libraries in the original architecture assumptions are now deprecated: `python-jose` (abandoned, last release 3 years ago) and `passlib` (unmaintained, breaks on Python 3.12+). FastAPI's official documentation has been updated to recommend `PyJWT` and `pwdlib[argon2]` respectively. Using the deprecated libraries will produce warnings at startup and create a security liability. Use the replacements from the outset.

For the token storage decision (Claude's Discretion): use HttpOnly cookies for the refresh token and `Authorization: Bearer` header for the access token. The refresh token never touches JavaScript, preventing XSS theft. The access token is short-lived (1 hour) and stored in React memory (not localStorage). This hybrid approach is the 2025 security consensus for SPAs communicating with REST APIs. CSRF must be addressed separately via SameSite=Lax cookie attribute (adequate for same-site deployments).

**Primary recommendation:** Build backend-first (FastAPI + DB + auth endpoints verified via Swagger UI) before touching the frontend. This sequence avoids integration surprises and lets the OpenAPI spec drive the React API client.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115+ | Web framework, auto-generates OpenAPI | Only major Python framework with built-in OpenAPI + async support |
| SQLAlchemy | 2.0+ | ORM with async support | Industry standard; 2.x async-native API removes sync footguns |
| asyncpg | 0.29+ | PostgreSQL async driver | Required by SQLAlchemy async engine; best performing Pg driver |
| Alembic | 1.13+ | Database migrations | SQLAlchemy's official migration tool; async-capable |
| PyJWT | 2.x | JWT token encoding/decoding | Actively maintained; FastAPI official docs updated to recommend this |
| pwdlib[argon2] | 0.2+ | Password hashing | FastAPI official replacement for deprecated passlib; Argon2 is best-in-class |
| pydantic-settings | 2.x | Environment config management | FastAPI-native settings; reads .env + env vars with type validation |
| uvicorn | 0.30+ | ASGI server | FastAPI's recommended production server |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | 0.0.9+ | Form data parsing | Required for OAuth2PasswordRequestForm (login endpoint) |
| httpx | 0.27+ | Async HTTP client for tests | FastAPI's recommended test client (async-compatible) |
| pytest-asyncio | 0.23+ | Async test support | Required for testing async FastAPI endpoints |
| React | 18.x | Frontend framework | Locked in architecture |
| React Router | 6.x | Client-side routing | v6 Outlet pattern simplifies protected route layouts |
| react-query (TanStack Query) | 5.x | Server state + caching | Standard for REST API data fetching in React; handles loading/error states |
| shadcn/ui | latest | Component library | Locked in architecture; composable, Tailwind-native |
| Tailwind CSS | 4.x | Utility CSS | New v4 uses `@import "tailwindcss"` without tailwind.config.ts by default |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose | python-jose is abandoned; do NOT use it |
| pwdlib[argon2] | passlib[bcrypt] | passlib is unmaintained, breaks Python 3.12+; do NOT use it |
| pwdlib[argon2] | direct bcrypt | Acceptable, but pwdlib is simpler and matches FastAPI docs |
| React Router v6 | TanStack Router | TanStack Router is newer/type-safer but React Router v6 is mature and widely documented |
| TanStack Query | SWR | Both acceptable; TanStack Query has better DevTools and more ecosystem support |
| HttpOnly cookie refresh | localStorage | localStorage is vulnerable to XSS; do NOT store refresh tokens there |

**Installation (backend):**
```bash
pip install "fastapi[standard]" "sqlalchemy[asyncio]>=2.0" asyncpg "alembic>=1.13" \
    pyjwt "pwdlib[argon2]" "pydantic-settings>=2.0" python-multipart uvicorn
```

**Installation (frontend):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom @tanstack/react-query axios
# Initialize shadcn/ui
npx shadcn@latest init
# Add components
npx shadcn@latest add sidebar button input label card separator avatar dropdown-menu
```

---

## Architecture Patterns

### Recommended Project Structure

Per ARCHITECTURE.md (authoritative for this project):
```
backend/app/
├── main.py              # FastAPI app factory, CORS, router registration
├── core/
│   ├── config.py        # pydantic-settings Settings class
│   ├── database.py      # async engine, session maker, Base
│   ├── security.py      # JWT encode/decode, password hash/verify
│   ├── dependencies.py  # get_db, get_current_user Depends()
│   └── exceptions.py    # Custom HTTPException subclasses
├── models/
│   └── user.py          # User, UserSession SQLAlchemy models
├── schemas/
│   └── user.py          # Pydantic request/response schemas
├── api/v1/
│   ├── router.py        # include_router calls
│   ├── auth.py          # /auth/login, /auth/refresh, /auth/logout, /auth/me
│   └── health.py        # /health, /health/ready
└── migrations/
    ├── env.py           # Alembic async env
    └── versions/

frontend/src/
├── main.tsx             # React app entry
├── App.tsx              # Router root
├── pages/              # (or app/) Route-level components
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx    # Placeholder
│   └── NotFoundPage.tsx
├── layouts/
│   ├── AuthLayout.tsx      # Public layout (login)
│   └── AppLayout.tsx       # Authenticated layout (sidebar + topbar)
├── components/
│   ├── AppSidebar.tsx      # shadcn/ui Sidebar composition
│   └── AppTopBar.tsx       # User info + logout
├── hooks/
│   └── useAuth.ts          # Auth context/state hook
├── services/
│   └── api.ts              # Axios instance, token attach, refresh logic
└── types/
    └── auth.ts             # Token, User types
```

### Pattern 1: Async SQLAlchemy Session Dependency

**What:** Inject an async database session per request using FastAPI's `Depends()`.
**When to use:** Every route handler that needs DB access.

```python
# Source: https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/
# backend/app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

engine = create_async_engine(
    settings.DATABASE_URL,  # postgresql+asyncpg://user:pass@host/db
    echo=settings.DEBUG,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# backend/app/core/dependencies.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

### Pattern 2: JWT Access + Refresh Token Auth

**What:** Issue short-lived access token (1h) + long-lived refresh token (7d) stored in HttpOnly cookie.
**When to use:** Login endpoint; protected by `get_current_user` dependency everywhere else.

```python
# Source: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
# backend/app/core/security.py
import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone

password_hash = PasswordHash.recommended()

def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, settings.JWT_SECRET_KEY, algorithm="HS256")

def create_refresh_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({**data, "exp": expire, "type": "refresh"}, settings.JWT_SECRET_KEY, algorithm="HS256")

def verify_password(plain: str, hashed: str) -> bool:
    return password_hash.verify(plain, hashed)

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)
```

```python
# backend/app/api/v1/auth.py — login endpoint
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Store hashed refresh token in user_sessions
    await create_session(db, user.id, refresh_token)

    # Refresh token in HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,        # HTTPS only in production
        samesite="lax",
        max_age=7 * 24 * 3600,
    )

    return {"access_token": access_token, "token_type": "bearer", "expires_in": 3600}
```

### Pattern 3: get_current_user Dependency

**What:** Verify JWT bearer token on protected routes.
**When to use:** As `Depends()` on every protected endpoint.

```python
# backend/app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user
```

### Pattern 4: FastAPI App Factory

**What:** Create the FastAPI app with all middleware and routers registered.
**When to use:** main.py — this is the entry point.

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router

app = FastAPI(
    title="CloudCost API",
    version="1.0.0",
    docs_url="/api/docs",      # AUTH-03: OpenAPI docs at /api/docs
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["https://cloudcost.fileread.com", "http://localhost:3000"]
    allow_credentials=True,               # Required for HttpOnly cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
```

### Pattern 5: React Protected Routes with Outlet

**What:** Wrap authenticated routes in a layout component that checks auth status.
**When to use:** All post-login routes that require the sidebar+topbar shell.

```tsx
// frontend/src/layouts/AppLayout.tsx
import { Navigate, Outlet } from "react-router-dom";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { AppTopBar } from "@/components/AppTopBar";
import { useAuth } from "@/hooks/useAuth";

export function AppLayout() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div>Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <SidebarProvider>
      <AppSidebar />
      <div className="flex flex-col flex-1">
        <AppTopBar />
        <main className="flex-1 p-6">
          <Outlet />  {/* Child routes render here */}
        </main>
      </div>
    </SidebarProvider>
  );
}

// frontend/src/App.tsx
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <AppLayout />,
    children: [
      { path: "/dashboard", element: <DashboardPage /> },
      // Future phases add routes here
    ],
  },
]);
```

### Pattern 6: Alembic Async Migration Setup

**What:** Configure Alembic to work with async SQLAlchemy engine.
**When to use:** Migration setup (one-time), and when creating new migrations.

```bash
# Initialize with async template
alembic init -t async migrations
```

```python
# migrations/env.py key additions
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.core.database import Base
# CRITICAL: import all models so autogenerate can see them
from app.models import user  # noqa: F401

target_metadata = Base.metadata

def get_url():
    return os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
```

### Anti-Patterns to Avoid

- **Using python-jose:** Import `jwt` from PyJWT, not `from jose import jwt`. The package names differ — using python-jose causes deprecation warnings on Python 3.12+.
- **Using passlib:** Import `from pwdlib import PasswordHash`, not `from passlib.context import CryptContext`. passlib's `crypt` module is removed in Python 3.13.
- **Storing refresh token in localStorage:** Never do this — XSS attacks can steal it. Always use HttpOnly cookie.
- **Storing access token in cookie:** Avoid — causes CSRF complexity. Keep access token in memory only.
- **Running migrations inside FastAPI startup:** Use Alembic CLI or a pre-start script. Running `alembic upgrade head` inside `@app.on_event("startup")` with async engine has known context issues.
- **Wildcard CORS origins in production:** Use exact origin list. `allow_origins=["*"]` with `allow_credentials=True` is invalid (browsers reject it).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT encode/decode | Custom base64 manipulation | `PyJWT` | Handles algorithm selection, expiry, signature verification correctly |
| Password hashing | Custom crypto | `pwdlib[argon2]` | Argon2 is properly tuned against GPU attacks; bcrypt has known cost issues |
| OpenAPI docs | Custom Swagger HTML | FastAPI built-in at `docs_url="/api/docs"` | Zero config, automatically reflects all registered routes |
| Database migrations | Raw SQL files + runner | `Alembic` | Handles schema diffing, downgrades, multi-db support |
| Settings management | os.environ.get() everywhere | `pydantic-settings` | Type coercion, validation, .env loading, test overrides |
| Auth dependency injection | Manual token parsing in each route | `FastAPI Depends(get_current_user)` | DRY; FastAPI auto-includes in OpenAPI security schema |
| React sidebar component | Custom CSS sidebar | `shadcn/ui add sidebar` | Keyboard navigation, collapsible state, accessible |

**Key insight:** FastAPI's OpenAPI integration means `docs_url="/api/docs"` in the FastAPI constructor is the entire implementation for API-03. No additional code required.

---

## Common Pitfalls

### Pitfall 1: python-jose and passlib Still Installed

**What goes wrong:** Python 3.12+ prints deprecation warnings on every startup. Python 3.13 removes `crypt` entirely, breaking passlib at import time.
**Why it happens:** Old tutorials, ARCHITECTURE.md references, and Stack Overflow use these libraries.
**How to avoid:** Use PyJWT (import as `import jwt`) and pwdlib. Don't even install python-jose.
**Warning signs:** `DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13` at startup.

### Pitfall 2: CORS + HttpOnly Cookies Misconfiguration

**What goes wrong:** Browser blocks cookie from being sent to API, OR browser blocks API response — login succeeds but subsequent requests fail with 401/CORS errors.
**Why it happens:** `allow_credentials=True` requires explicit `allow_origins` list (never `"*"`). Frontend Axios must have `withCredentials: true`. Cookie domain must match.
**How to avoid:**
- Backend: `allow_credentials=True` + explicit origins list
- Frontend: `axios.defaults.withCredentials = true`
- Cookie: `SameSite=Lax` (works for same-site; `Strict` blocks cross-origin redirects)
**Warning signs:** Browser console shows "CORS error" or "credentialed request" error.

### Pitfall 3: Alembic autogenerate Missing Models

**What goes wrong:** `alembic revision --autogenerate` generates empty migration even though models exist.
**Why it happens:** Alembic's `env.py` must import all SQLAlchemy model modules so they register with `Base.metadata` before autogenerate runs.
**How to avoid:** Add `from app.models import user, cloud, billing  # noqa` imports in `env.py` before `target_metadata = Base.metadata`.
**Warning signs:** Empty `upgrade()` function in generated migration file.

### Pitfall 4: Async SQLAlchemy Lazy Loading After Commit

**What goes wrong:** Accessing a relationship attribute after `await db.commit()` raises `MissingGreenlet` or `DetachedInstanceError`.
**Why it happens:** SQLAlchemy async sessions don't support lazy loading. After commit, the session expires instances.
**How to avoid:** Use `expire_on_commit=False` on `async_sessionmaker`. For relationships, use `selectinload()` or `joinedload()` in the query.
**Warning signs:** `MissingGreenlet: greenlet_spawn has not been called` at runtime.

### Pitfall 5: FastAPI Docs URL Conflict

**What goes wrong:** Swagger UI not accessible at `/api/docs`.
**Why it happens:** FastAPI's default `docs_url="/docs"` is at root; the architecture requires `/api/docs`.
**How to avoid:** Set `docs_url="/api/docs"` in `FastAPI()` constructor, not via router prefix.
**Warning signs:** 404 at `/api/docs`, works at `/docs`.

### Pitfall 6: React Router and Vite Dev Proxy

**What goes wrong:** API calls from React dev server fail with CORS errors even though backend CORS is correctly configured.
**Why it happens:** In dev, React runs on port 3000, FastAPI on 8000 — different origins. Docker Compose networking and browser CORS rules differ.
**How to avoid:** Configure Vite dev proxy in `vite.config.ts`:
```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```
OR ensure cookies work cross-origin with `SameSite=None; Secure` in dev (requires HTTPS).
**Warning signs:** CORS errors only in browser, not in curl/Postman.

### Pitfall 7: Admin Seed User Bootstrap

**What goes wrong:** Application deployed, no way to log in — first admin account doesn't exist.
**Why it happens:** No one built a seed mechanism before shipping.
**How to avoid:** Create `backend/app/scripts/seed_admin.py` that checks for existing admin and creates one from environment variables (`FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_PASSWORD`). Run as: `docker compose exec api python -m app.scripts.seed_admin`. This is the simplest approach for a solo developer.

---

## Code Examples

Verified patterns from official sources:

### pydantic-settings Config Pattern

```python
# Source: https://fastapi.tiangolo.com/advanced/settings/
# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    FIRST_ADMIN_EMAIL: str = ""
    FIRST_ADMIN_PASSWORD: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### Health Endpoint

```python
# backend/app/api/v1/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    # Ping DB — Claude's Discretion: include DB ping for readiness
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    if not db_ok:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready", "database": "ok"}
```

### Axios API Client with Token Refresh

```typescript
// Source: Standard pattern verified across multiple guides
// frontend/src/services/api.ts
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1",
  withCredentials: true, // Send HttpOnly refresh token cookie
});

// Attach access token from memory to every request
api.interceptors.request.use((config) => {
  const token = getAccessToken(); // from memory/context, never localStorage
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401, attempt token refresh
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      const { data } = await api.post("/auth/refresh"); // cookie auto-sent
      setAccessToken(data.access_token); // store in memory
      error.config.headers.Authorization = `Bearer ${data.access_token}`;
      return api(error.config);
    }
    return Promise.reject(error);
  }
);

export default api;
```

### shadcn/ui Sidebar Composition

```tsx
// Source: https://ui.shadcn.com/docs/components/radix/sidebar
// frontend/src/components/AppSidebar.tsx
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
} from "@/components/ui/sidebar";
import { LayoutDashboard, AlertTriangle, Lightbulb, Users, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Anomalies", url: "/anomalies", icon: AlertTriangle },
  { title: "Recommendations", url: "/recommendations", icon: Lightbulb },
  { title: "Attribution", url: "/attribution", icon: Users },
  { title: "Settings", url: "/settings", icon: Settings },
];

export function AppSidebar() {
  return (
    <Sidebar>
      <SidebarHeader>
        <span className="font-bold text-lg px-2">CloudCost</span>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink to={item.url}>
                      <item.icon />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
```

### Dockerfile (Backend)

```dockerfile
# Source: https://fastapi.tiangolo.com/deployment/docker/
FROM python:3.12-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

# Azure Container Apps uses HTTP health probes — map to /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Exec form required for proper signal handling and FastAPI shutdown
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `from jose import jwt` (python-jose) | `import jwt` (PyJWT) | 2024 | python-jose abandoned; FastAPI docs updated |
| `from passlib.context import CryptContext` | `from pwdlib import PasswordHash` | 2024 | passlib unmaintained; breaks Python 3.12+ |
| `tiangolo/uvicorn-gunicorn-fastapi` Docker image | Plain `python:3.12-slim` + uvicorn | 2023+ | Base image deprecated by tiangolo himself |
| `SQLAlchemy 1.x` sync sessions | `SQLAlchemy 2.0` async-native API | 2023 | 2.x has cleaner async ergonomics; 1.x patterns cause runtime errors |
| `tailwind.config.ts` + PostCSS | `@import "tailwindcss"` in CSS (v4) | 2024 | Tailwind v4 changes config; shadcn/ui docs now use v4 setup |
| `from fastapi import BackgroundTasks` for token rotation | Celery tasks (Phase 2+) | N/A | BackgroundTasks adequate for Phase 1 session cleanup |

**Deprecated/outdated:**
- `python-jose`: Do not install. Last release 3 years ago.
- `passlib`: Do not install. Breaks at import time on Python 3.13.
- `tiangolo/uvicorn-gunicorn-fastapi Docker image`: Deprecated by its creator; use python:3.12-slim directly.
- Tailwind v3 `tailwind.config.ts` approach: shadcn/ui now assumes v4.

---

## Claude's Discretion Recommendations

### Token Storage Strategy
**Decision: HttpOnly cookie for refresh token, memory-only for access token.**

Rationale: This is the 2025 security consensus for SPAs. The refresh token (7-day, high-value) never touches JavaScript, preventing XSS theft. The access token (1-hour, low-risk) lives in React state/context. localStorage is explicitly not used. CSRF risk with SameSite=Lax cookies is acceptable for same-site deployments.

Implementation note: `allow_credentials=True` in FastAPI CORS middleware is required for cookies to work cross-origin. The frontend Axios instance must have `withCredentials: true`.

### Admin Bootstrap
**Decision: Environment variable seed script.**

Create `backend/app/scripts/seed_admin.py`. On first run (or whenever called), check if any admin user exists. If not, create one from `FIRST_ADMIN_EMAIL` + `FIRST_ADMIN_PASSWORD` env vars. Document in README. Run once manually: `docker compose exec api python -m app.scripts.seed_admin`. This is the simplest reliable approach — no endpoint exposure, no special UI, no DB dependency at startup.

### Health Check Depth
**Decision: Two endpoints — liveness at /health (app-only), readiness at /health/ready (with DB ping).**

Azure Container Apps supports both liveness and readiness probes. `/health` returns 200 immediately (used for liveness — is the container alive?). `/health/ready` pings the database with `SELECT 1` (used for readiness — is the container ready to serve traffic?). This is the Azure Container Apps best practice pattern.

### Login Page UX
- Inline validation feedback after first blur (not on every keystroke)
- Password visibility toggle using shadcn/ui Button + Input composition
- Loading spinner on submit button
- Error message displayed as `Alert` component below the form
- No redirect loop complexity needed — simple: if `!user`, show login form; on success, navigate to `/dashboard`

---

## Open Questions

1. **Python 3.12 vs 3.13**
   - What we know: ARCHITECTURE.md specifies Python 3.11+; FastAPI docs now show Python 3.14 in examples
   - What's unclear: Whether asyncpg 0.29+ is stable on Python 3.13 (some compatibility notes found)
   - Recommendation: Use Python 3.12 for the Docker image (stable, well-tested with asyncpg). Test before upgrading to 3.13.

2. **Tailwind v3 vs v4**
   - What we know: shadcn/ui official docs show Tailwind v4 setup (`@import "tailwindcss"`, no tailwind.config.ts)
   - What's unclear: Whether all shadcn/ui components are fully tested with Tailwind v4 or if some components have v3-only styling
   - Recommendation: Follow shadcn/ui's official Vite installation guide exactly — it will install the correct Tailwind version.

3. **Azure Container Apps CORS headers**
   - What we know: Azure Container Apps terminates TLS and proxies to the container
   - What's unclear: Whether Azure adds its own CORS headers that could conflict with FastAPI's CORSMiddleware
   - Recommendation: Include `--proxy-headers` in the uvicorn CMD so FastAPI correctly reads X-Forwarded-For. Test CORS end-to-end after first deploy.

---

## Sources

### Primary (HIGH confidence)
- `https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/` — PyJWT + pwdlib patterns (fetched directly)
- `https://fastapi.tiangolo.com/deployment/docker/` — Dockerfile pattern (fetched directly)
- `https://ui.shadcn.com/docs/installation/vite` — shadcn/ui Vite setup (fetched directly)
- `https://ui.shadcn.com/docs/components/radix/sidebar` — Sidebar component patterns (fetched directly)
- `https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/` — async SQLAlchemy 2 + Alembic patterns (fetched directly)

### Secondary (MEDIUM confidence)
- `https://github.com/fastapi/fastapi/discussions/11345` — python-jose abandonment discussion (multiple sources confirm)
- `https://github.com/fastapi/fastapi/pull/11589` — FastAPI docs update to PyJWT (official PR)
- `https://github.com/fastapi/fastapi/discussions/11773` — passlib maintenance discussion
- `https://learn.microsoft.com/en-us/azure/container-apps/health-probes` — Azure Container Apps health probes
- `https://blog.greeden.me/en/2025/10/14/...` — FastAPI security best practices 2025

### Tertiary (LOW confidence)
- WebSearch results on React Router v6 protected routes pattern (consistent across multiple sources; elevated to MEDIUM)
- WebSearch results on TanStack Query v5 as React state management (widely recommended but not fetched from docs)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against official FastAPI docs; library deprecations confirmed via GitHub discussions + official PR
- Architecture: HIGH — canonical structure pre-defined in ARCHITECTURE.md; patterns verified against official sources
- Pitfalls: HIGH — python-jose/passlib deprecation confirmed via multiple official sources; async SQLAlchemy pitfalls documented in SQLAlchemy 2.0 migration guide
- Token storage: HIGH — 2025 consensus from multiple security-focused sources, consistent recommendation

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (30 days; FastAPI + shadcn/ui are relatively stable; check PyPI for patch updates)
