# Trading212 App — Architecture Design

> Status: **Approved Draft — Phase 1 in progress**
> Last updated: 2026-04-14

---

## 1. Goal

Build a professional, Dockerised Python application that connects to the Trading212 Public API to:
1. **Manually** place buy/sell market orders via CLI (Phase 1 — validates the integration safely)
2. **Automatically** execute signal-based trading strategies (Phase 2)

---

## 2. Decisions (locked)

| Question | Decision |
|---|---|
| Primary use case | Signal-based trading |
| Phase 1 | Manual buy/sell CLI to validate API safely |
| Trade log | Yes — SQLite, append-only |
| Deployment | Docker container |
| Paper trading | Yes — `--dry-run` flag + `PAPER_MODE=true` env |
| Publishing | GitHub, with professional git workflow |

---

## 3. Trading212 API — Key Facts

| Property | Detail |
|---|---|
| Base URL (live) | `https://live.trading212.com/api/v0` |
| Auth | `Authorization: <api-key>` header |
| Rate limiting | Per-account; `x-ratelimit-remaining` / `x-ratelimit-reset` headers |
| Order types (live) | **Market orders only** via API |
| Functional limits | Max 50 pending orders per ticker per account |

### Endpoint groups used

| Group | Endpoints |
|---|---|
| Account | `GET /equity/account/info` |
| Portfolio | `GET /equity/portfolio` |
| Orders | `POST /equity/orders/market`, `DELETE /equity/orders/{id}`, `GET /equity/orders` |
| Instruments | `GET /equity/instruments` |
| History | `GET /equity/history/orders` |

---

## 4. Architecture

### 4.1 Project layout

```
trading212/
├── .env.example                # Template — never commit .env
├── .gitignore
├── .pre-commit-config.yaml     # ruff + mypy hooks
├── pyproject.toml              # uv-managed deps, tool config
├── docker-compose.yml          # Local dev + prod-like run
├── Dockerfile
├── DESIGN.md
│
├── .github/
│   └── workflows/
│       └── ci.yml              # lint → typecheck → test on every PR
│
├── src/
│   └── t212/
│       ├── __init__.py
│       ├── cli.py              # Typer entry point
│       ├── client.py           # httpx API client, auth, rate-limit backoff
│       ├── models.py           # Pydantic v2 models (Account, Position, Order…)
│       ├── portfolio.py        # Portfolio queries + rich display
│       ├── orders.py           # Buy/sell logic, validation, dry-run
│       ├── db.py               # SQLite trade log
│       ├── config.py           # pydantic-settings, loads .env
│       └── strategy/
│           ├── __init__.py
│           ├── engine.py       # Signal evaluator loop
│           └── signals.py      # Signal definitions (price-drop, RSI, MA…)
│
└── tests/
    ├── conftest.py
    ├── test_client.py
    ├── test_orders.py
    ├── test_portfolio.py
    └── test_strategy.py
```

### 4.2 Component responsibilities

| Component | Responsibility |
|---|---|
| `config.py` | Load + validate all env vars; single config object used everywhere |
| `client.py` | All HTTP to Trading212: auth headers, rate-limit-aware backoff, retries, paper-mode short-circuit |
| `models.py` | Pydantic models mirroring API shapes — single source of truth for data |
| `portfolio.py` | Fetch + display positions, account balance, P&L summary |
| `orders.py` | Place/cancel market orders, pre-flight validation, dry-run logging |
| `strategy/` | Evaluate signals against live data; emit `BuySignal` / `SellSignal` decisions |
| `db.py` | Append-only SQLite log of every attempted order (real and dry-run) |
| `cli.py` | User-facing Typer commands |

### 4.3 Data flow

```
CLI command
    │
    ▼
config.py  ──► validates env, sets PAPER_MODE
    │
    ▼
client.py  ──► authenticated httpx calls to Trading212
    │             rate-limit backoff + retry built in
    ▼
models.py  ──► parse + validate API responses
    │
    ▼
orders.py / portfolio.py / strategy/
    │
    ▼
db.py      ──► log every action to SQLite
    │
    ▼
CLI output (rich tables)
```

---

## 5. CLI Commands

```bash
# --- Portfolio ---
t212 portfolio                              # show open positions + P&L

# --- Manual trading (Phase 1) ---
t212 buy  --ticker AAPL --amount 50        # buy £50 worth
t212 sell --ticker AAPL --quantity 2       # sell 2 shares
t212 orders                                # list active orders
t212 cancel --order-id <id>               # cancel an order

# --- Dry-run (paper trading) ---
t212 buy --ticker AAPL --amount 50 --dry-run

# --- Strategy (Phase 2) ---
t212 strategy run                          # evaluate signals once
t212 strategy watch --interval 15m        # run on a schedule
t212 strategy list                         # list configured signals

# --- Trade log ---
t212 log                                   # show recent trade log entries
```

---

## 6. Configuration (`.env`)

```dotenv
# Required
T212_API_KEY=your_api_key_here

# Safety
PAPER_MODE=true          # true = no real orders ever sent
MAX_ORDER_GBP=100        # hard cap per single order
TRADING_ENABLED=true     # master kill-switch

# Optional
LOG_LEVEL=INFO
DB_PATH=/data/trades.db
```

---

## 7. Paper Trading

- `PAPER_MODE=true` in env **or** `--dry-run` flag on any command
- In paper mode: API reads work normally (real portfolio data), but order POSTs are intercepted before sending
- All paper orders are logged to SQLite with `dry_run=true` column
- Output clearly labelled `[DRY RUN]` in the terminal

---

## 8. Docker

```yaml
# docker-compose.yml (sketch)
services:
  t212:
    build: .
    env_file: .env
    volumes:
      - ./data:/data    # SQLite persisted outside container
    restart: unless-stopped
```

- `data/` volume persists the SQLite DB across container restarts
- Single image, no external DB dependency
- `Dockerfile` uses multi-stage build: build deps → slim runtime image

---

## 9. Tech Stack

| Role | Library |
|---|---|
| HTTP client | `httpx` (sync, with retry via `tenacity`) |
| Data models | `pydantic` v2 |
| CLI | `typer` + `rich` (tables, colour output) |
| Config / env | `pydantic-settings` |
| Storage | `sqlite3` (stdlib) |
| Scheduling (Phase 2) | `APScheduler` |
| Testing | `pytest` + `respx` (httpx mocking) + `pytest-cov` |
| Linting | `ruff` |
| Type checking | `mypy` |
| Package manager | `uv` |

---

## 10. Git & Release Workflow

### Branch strategy

```
main          ← production-ready, protected
  └── develop ← integration branch
        ├── feat/manual-orders
        ├── feat/trade-log
        ├── feat/paper-mode
        └── feat/strategy-engine   (Phase 2)
```

### Commit convention — Conventional Commits

```
feat(orders): add market buy command
fix(client): handle 429 rate-limit with backoff
chore(deps): bump httpx to 0.28
docs(design): lock phase 1 decisions
test(orders): add dry-run order tests
```

### PR rules
- Every feature lives on a branch
- PR → `develop`, reviewed (even self-reviewed) before merge
- Squash merge to keep `develop` history clean
- `develop` → `main` via PR when a phase is complete

### CI (GitHub Actions on every PR)
```
1. ruff check     (lint)
2. mypy           (type check)
3. pytest         (tests with coverage)
```

### Versioning
- Semantic versioning: `v0.1.0` (Phase 1 complete), `v0.2.0` (Phase 2), etc.
- Git tags on `main` after each release

---

## 11. Phases

### Phase 1 — Manual Trading (current)
- [ ] Project scaffold (pyproject.toml, Dockerfile, CI, .gitignore)
- [ ] `config.py` — env loading + validation
- [ ] `client.py` — authenticated httpx client + rate-limit backoff
- [ ] `models.py` — Account, Position, Order pydantic models
- [ ] `portfolio.py` — fetch + display portfolio
- [ ] `orders.py` — buy/sell + cancel + paper mode
- [ ] `db.py` — SQLite trade log
- [ ] `cli.py` — all Phase 1 commands
- [ ] Tests for all above
- [ ] Docker build working
- [ ] Release `v0.1.0`

### Phase 2 — Signal-Based Trading
- [ ] `strategy/signals.py` — price-drop, MA crossover, RSI signals
- [ ] `strategy/engine.py` — signal evaluation loop
- [ ] `cli.py` — `strategy` command group
- [ ] APScheduler integration
- [ ] Release `v0.2.0`
