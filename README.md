# Project Vertex — Atomic State Sync Engine

Project Vertex is a production-grade, end-to-end implementation of an atomic state synchronization engine. It links two abstract node entities via secure, opaque, time-bound reference tokens. It features a FastAPI backend with column-level row-level security (RLS) policies in PostgreSQL, and a mobile-first React/TypeScript frontend incorporating optimistic UI updates, camera hardware scanning, and client-side list virtualization.

---

## 1. Architecture Overview

```
                          ┌───────────────────────────┐
                          │     React 18 Frontend     │
                          │   (Vite + TS + Zustand)   │
                          └─────────────┬─────────────┘
                                        │
                               HTTP POST / GET
                                        │
                       ┌────────────────▼────────────────┐
                       │         FastAPI Server          │
                       │     (app.services.* layers)     │
                       └────────────────┬────────────────┘
                                        │
                                 SQL / pg_transport
                                        │
                       ┌────────────────▼────────────────┐
                       │     PostgreSQL 16 Database      │
                       │  (Unique Constraints + RLS)     │
                       └─────────────────────────────────┘
```

The system is structured as three distinct operational layers:
1. **Frontend Application Layer:** Drives the user interface. It utilizes a **Zustand** state store for modular async management. Network requests use a fetch client supporting exponential backoff retries and abort signals for timeouts.
2. **Backend Service Layer:** Constructed with **FastAPI**. Thin endpoints delegate immediately to dedicated services (`token_service`, `sync_service`, `link_service`, `entity_service`).
3. **Database Security & Constraint Layer:** Built on **PostgreSQL 16**. Data integrity and access constraints are enforced natively in the database via unique indices and role-based Column-Level Privileges combined with Row-Level Security (RLS).

---

## 2. Data Structures & Schema

```
┌─────────────────────────────────┐
│            entities             │
├─────────────────────────────────┤
│ id: UUID (PK)                   │
│ label: VARCHAR(255)             │
│ owner_role: VARCHAR(50)         │
│ created_at: TIMESTAMPTZ         │
└──────────────┬──────────────────┘
               │ 1
               │
               │ 0..*
┌──────────────▼──────────────────┐
│        reference_tokens         │
├─────────────────────────────────┤
│ id: UUID (PK)                   │
│ kid: VARCHAR(64)                │
│ token_hash: VARCHAR(64) (UQ)    │
│ entity_id: UUID (FK -> entities)│
│ expires_at: TIMESTAMPTZ         │
│ used_at: TIMESTAMPTZ (Nullable) │
│ created_at: TIMESTAMPTZ         │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│             links               │
├─────────────────────────────────┤
│ id: UUID (PK)                   │
│ entity_a_id: UUID (FK)          │
│ entity_b_id: UUID (FK)          │
│ private_notes: TEXT             │
│ created_at: TIMESTAMPTZ         │
└─────────────────────────────────┘
```

### Concurrency-Safety Mechanism: Unique Composite Constraint + Canonical Ordering
To prevent race conditions and duplicate link insertions (e.g., when two nodes attempt to sync simultaneously or a client fires rapid concurrent requests), we implement:
1. **Canonical ID Ordering:** Before inserting a link, the application compares the UUIDs of the two entities lexicographically. The smaller UUID is mapped to `entity_a_id` and the larger to `entity_b_id`.
2. **Unique Composite Constraint:** A database-level constraint `uq_links_pair` covers `(entity_a_id, entity_b_id)`.
3. **INSERT ON CONFLICT DO NOTHING:** The sync endpoint issues an atomic raw SQL insert using `ON CONFLICT (entity_a_id, entity_b_id) DO NOTHING`. If a link already exists, the insert yields empty results. The service then falls back to a SELECT to return the existing record.

**Why not `SELECT ... FOR UPDATE` row locking?**
Row locking requires querying parent entities with `FOR UPDATE` before executing updates. In high-concurrency environments, if Request A locks `Entity 1` then `Entity 2`, and Request B locks `Entity 2` then `Entity 1`, a database deadlock occurs. The Unique Constraint + ON CONFLICT model is completely **deadlock-free**, lightning fast, and delegates safety directly to Postgres's index engine.

### Row-Level Security & Column-Level Privilege Design
To strictly isolate sensitive metadata (`private_notes`) from administrative roles at the database layer:
1. We define two separate database roles: `app_user` (regular client connections) and `app_admin` (administrative tools).
2. We enable RLS on the `links` table:
   ```sql
   ALTER TABLE links ENABLE ROW LEVEL SECURITY;
   ALTER TABLE links FORCE ROW LEVEL SECURITY;
   ```
3. We configure role-based access policies:
   * `app_user` gets complete read/write access to all links.
   * `app_admin` is explicitly granted SELECT on only structural columns, but the private metadata column is revoked:
     ```sql
     GRANT SELECT (id, entity_a_id, entity_b_id, created_at) ON links TO app_admin;
     -- Notice: 'private_notes' is NOT included in the selection privilege!
     ```
   * If a query connected as `app_admin` attempts to read `private_notes`, PostgreSQL immediately aborts the query execution with an `InsufficientPrivilegeError`, ensuring metadata containment even if application-level filters fail.

---

## 3. Token Design

Project Vertex issues opaque, signed reference tokens rather than client-readable JWTs.

### Token Construction & Verification Lifecycle
1. **Generation:** When a node requests a token, the backend generates a cryptographically random payload:
   $$\text{raw\_token} = \text{base64url}(\text{kid} + \text{"."} + \text{random\_bytes(32)})$$
2. **Hashing:** The server computes an HMAC-SHA256 signature of the raw token using the secret matching the active `kid` (Key Rotation ID). The resulting `token_hash` is saved to the database. The `raw_token` is returned to the client and **never** stored.
3. **Verification:** When presenting the token to `/api/state/sync`, the server:
   * Parses the `kid` from the raw token prefix.
   * Looks up the corresponding secret in configuration.
   * Computes the HMAC-SHA256 hash and compares it in **constant-time** (`hmac.compare_digest`) against the hash in the database.
   * Validates that `expires_at > now()`.
   * Asserts replay protection by verifying `used_at IS NULL`.
4. **Replay Protection:** To enforce single-use lifecycle, the server updates `used_at` to the current timestamp inside the **same atomic database transaction** as the link creation. If concurrent requests try to reuse the token, the row-locked (`SELECT FOR UPDATE`) token consumption path rejects subsequent requests with a `409 Conflict`.

---

## 4. State Management Rationale

The frontend uses **Zustand** to construct an async-driven state machine.

### Optimistic UI & Reconciliation State Model
To eliminate perceived latency during mobile scans, the interface gives instant feedback before the server handshake completes:
1. **Transition to Optimistic State:** When a user initiates sync, the store creates a temporary link with a placeholder ID (`temp-timestamp`) and prepends it to the link list. The state status transitions to `optimistic`.
2. **Server Handshake:** The API request fires.
3. **Reconciliation:**
   * **On Success:** The store replaces the temporary optimistic card with the confirmed, fully-populated link object returned by the server, updating the status to `confirmed`.
   * **On Failure (Rollback):** If the network times out or the server returns an error (e.g., token expired or replayed), the store rolls back the links list to its cached previous state, sets the status to `error`, and surfaces a detailed feedback banner.

### Request Lifecycle States
The system maps operations to five explicit status states rather than binary booleans:
* `idle`: Default operational state.
* `pending`: Token verified, awaiting transaction start.
* `optimistic`: UI populated, server request in flight.
* `confirmed`: Server handshake succeeded, state verified.
* `error`: Handshake failed, state rolled back.

---

## 5. Scaling to 5,000 Concurrent Interactions

To support high-burst traffic of 5,000 concurrent actions, we deploy the following architectural optimizations:

1. **Connection Pooling (PgBouncer):** Run PgBouncer in transaction mode (`pool_mode = transaction`) between FastAPI and PostgreSQL. This allows thousands of app-server workers to share a small pool of persistent DB connections, preventing PG backend process limits from exhausting memory.
2. **Read/Write Bottlenecks:** Link creations (`POST /sync`) represent the write path, while directories (`GET /links`) represent the read path. We separate these paths by routing reads to read replicas, while routing writes and immediate token consumptions to the primary database node.
3. **Contention Resolution:** Under high contention, the deadlock-free Unique Composite Constraint (`ON CONFLICT DO NOTHING`) prevents table-level locks. While `SELECT FOR UPDATE` is used to consume individual token rows, each transaction locks only a single token record, avoiding cross-transaction contention.
4. **Token Cache Path:** To scale token validation, we cache token metadata in a Redis instance. Replay protection is enforced by placing a short-lived Redis lock/nonce on the token string before database execution.
5. **Horizontal Scaling & Rate Limiting:** FastAPI nodes scale horizontally inside an ECS or Kubernetes cluster behind an NGINX load balancer. We apply token bucket rate limiting at the load balancer level (e.g., max 10 requests/sec per client IP) to block DDoS or malfunctioning scanners.
6. **Frontend Perceived Latency:** The optimistic UI ensures the mobile user receives visual confirmation within 16ms of scanning, hiding the backend network latency of the load-balanced API handshake.

---

## 6. Local Setup

### Prerequisites
* Docker and Docker Compose
* Python 3.12 (if running backend tests locally)
* Node.js v18+ (if running frontend tests locally)

### Running with Docker Compose
1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Spin up the entire stack:
   ```bash
   docker-compose up --build
   ```
3. Access the services:
   * **Frontend Application:** [http://localhost:5173](http://localhost:5173)
   * **Backend Documentation (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)

### Database Migrations & Seed
Migrations apply automatically on backend startup. To run seeds manually inside the container:
```bash
docker-compose exec backend python -m app.db.seed
```

### Running the Test Suites

#### Backend Tests (SQLite / Mock DB)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

#### Backend RLS Integration Tests (Requires Postgres)
```bash
# Set env flag and run RLS database tests
set RLS_TESTS=1
pytest -m rls tests/test_rls.py
```

#### Frontend Tests (Vitest)
```bash
cd frontend
npm install
npm run test
```

---

## 7. Known Limitations & Next Steps
* **Browser Sandbox Camera restrictions:** `getUserMedia` requires a secure context (HTTPS or localhost). In production, SSL must be terminated at the load balancer for mobile scanners to open the camera stream.
* **Authentication Mocking:** A role switcher (`X-Role`) represents authentication. In production, this should integrate with a JWT/OAuth2 identity provider.
* **Local Memory Mocking for SQLite Tests:** Backend RLS tests require a real Postgres database because SQLite does not support PostgreSQL Row-Level Security policies. Consequently, `tests/test_rls.py` is skipped unless Postgres is active.
