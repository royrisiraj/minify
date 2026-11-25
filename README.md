# Minify

**Shorter links. Smarter connections.**

Minify is an open-source URL shortening and intelligent link management platform designed for performance, scalability, security, and simplicity.

Built with a backend-first engineering philosophy, Minify aims to transform long, cumbersome URLs into compact, manageable, and trackable links through a modern, scalable architecture.

---

## Overview

Minify is more than a conventional URL shortener. It is a full-stack link management system designed to explore and implement real-world software engineering principles, including:

- RESTful API architecture
- Distributed caching
- Database optimization
- Secure authentication and authorization
- High-performance URL redirection
- Event-driven analytics
- API rate limiting
- Abuse prevention
- Automated testing and deployment

The project aims to evolve from a lightweight URL shortening service into a production-ready link management platform.

## Project Status

**Status: Under Development**

The features and architecture documented below represent the intended development roadmap. Features will be marked as completed following implementation and verification.

## Features

### Core Functionality

- [ ] Instant URL shortening
- [ ] Unique short-code generation
- [ ] Automatic URL redirection
- [ ] URL validation
- [ ] Collision detection and resolution
- [ ] Custom URL aliases
- [ ] Clipboard integration

### Link Management

- [ ] User registration and authentication
- [ ] Personalized link management dashboard
- [ ] Edit and delete shortened URLs
- [ ] Link activation and deactivation
- [ ] Configurable expiration dates
- [ ] Password-protected links
- [ ] QR code generation

### Analytics

- [ ] Real-time click tracking
- [ ] Total and unique visitor estimates
- [ ] Geographic distribution
- [ ] Device and browser analytics
- [ ] Referrer tracking
- [ ] Time-series analytics
- [ ] Analytics export

### Performance and Scalability

- [ ] Redis-backed caching
- [ ] Optimized database indexing
- [ ] Asynchronous analytics processing
- [ ] Database connection pooling
- [ ] Cache expiration and invalidation
- [ ] Load testing and benchmarking
- [ ] Horizontal scaling support

### Security

- [ ] JWT-based authentication
- [ ] Secure password hashing
- [ ] API rate limiting
- [ ] Malicious URL detection
- [ ] Input sanitization and validation
- [ ] Unauthorized access prevention
- [ ] Reserved alias protection
- [ ] Abuse reporting

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript |
| Styling | Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Caching | Redis |
| Authentication | JWT |
| API Documentation | OpenAPI, Swagger UI |
| Backend Testing | Pytest |
| Frontend Testing | Vitest |
| Load Testing | Locust |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Frontend Deployment | Vercel |
| Backend Deployment | Render |
| Database Hosting | Neon |

---

## System Architecture

Minify follows a modular client-server architecture with distinct presentation, application, caching, and persistence layers.

```mermaid
flowchart TD
    A[Client / Browser] --> B[React Frontend]
    A -->|Short URL Request| C[FastAPI Backend]
    B -->|REST API| C

    C --> D[Authentication Layer]
    C --> E[URL Management Service]
    C --> F[Redirection Service]
    C --> G[Analytics Service]

    E --> H[PostgreSQL]
    F --> I[Redis Cache]
    I -->|Cache Miss| H
    F -->|Click Event| J[Event Queue]
    J --> G
    G --> H

    D --> H
    F -->|HTTP 302 Redirect| K[Original Destination]
```

*Target architecture. Redis and asynchronous event processing will be introduced in later development phases.*

## How It Works

### URL Shortening

1. A user submits a destination URL.
2. The backend validates the URL and its supported protocol.
3. A cryptographically secure random Base62 short code is generated.
4. The backend stores the URL mapping in PostgreSQL.
5. Database uniqueness constraints prevent duplicate short codes.
6. The shortened URL is returned to the user.

Example:

```text
Original URL:
https://example.com/articles/software-engineering/system-design

Shortened URL:
https://minify.example/a7X9kP2
```

### URL Redirection

1. A visitor accesses a shortened URL.
2. The backend extracts the short code.
3. Redis is checked for a cached URL mapping.
4. PostgreSQL is queried if the cache misses.
5. Link validity and expiration are evaluated.
6. A click event is recorded.
7. The visitor receives an HTTP redirect to the destination.

### Analytics Processing

Click events will be processed asynchronously to minimize their impact on redirection latency.

Analytics will provide aggregated insights while minimizing the collection and retention of personally identifiable information.

---

## Database Design

```mermaid
erDiagram
    USERS ||--o{ LINKS : owns
    LINKS ||--o{ CLICK_EVENTS : receives

    USERS {
        uuid id PK
        string email UK
        string password_hash
        datetime created_at
        datetime updated_at
    }

    LINKS {
        uuid id PK
        uuid user_id FK
        string original_url
        string short_code UK
        string password_hash
        boolean is_active
        datetime created_at
        datetime updated_at
        datetime expires_at
    }

    CLICK_EVENTS {
        uuid id PK
        uuid link_id FK
        string country
        string device_type
        string browser
        string referrer
        datetime clicked_at
    }
```

### Database Strategy

- Unique indexing on short codes for efficient URL resolution.
- Foreign key constraints for referential integrity.
- Composite indexing for time-based analytics.
- Transaction-safe URL creation.
- Controlled retention of analytics data.
- Version-controlled database migrations.

---

## API Reference

Base path:

```text
/api/v1
```

### URL Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/links` | Create a shortened URL |
| GET | `/api/v1/links` | Retrieve owned links |
| GET | `/api/v1/links/{id}` | Retrieve link details |
| PATCH | `/api/v1/links/{id}` | Update a link |
| DELETE | `/api/v1/links/{id}` | Delete a link |
| GET | `/{short_code}` | Redirect to destination |

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register an account |
| POST | `/api/v1/auth/login` | Authenticate user |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Terminate session |
| GET | `/api/v1/auth/me` | Retrieve current user |

### Analytics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/links/{id}/analytics` | Link analytics |
| GET | `/api/v1/links/{id}/analytics/timeline` | Click history |
| GET | `/api/v1/links/{id}/analytics/geography` | Geographic analytics |
| GET | `/api/v1/links/{id}/qr` | Generate QR code |

### System

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/ready` | Service readiness check |
| GET | `/docs` | Swagger API documentation |
| GET | `/redoc` | ReDoc API documentation |

### Example Request

```http
POST /api/v1/links
Content-Type: application/json
```

```json
{
  "original_url": "https://example.com/articles/system-design",
  "custom_alias": null,
  "expires_at": null
}
```

### Example Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "original_url": "https://example.com/articles/system-design",
  "short_code": "a7X9kP2",
  "short_url": "https://minify.example/a7X9kP2",
  "is_active": true,
  "created_at": "2026-11-25T00:00:00Z",
  "expires_at": null
}
```

The API contracts shown above are proposed interfaces and may evolve during development.

---

## Project Structure

```text
minify/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── links.py
│   │   │       └── analytics.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── exceptions.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── link.py
│   │   │   └── click_event.py
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── shortener.py
│   │   │   ├── redirect.py
│   │   │   ├── analytics.py
│   │   │   └── cache.py
│   │   ├── repositories/
│   │   ├── middleware/
│   │   ├── utils/
│   │   ├── database.py
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   ├── utils/
│   │   └── App.tsx
│   ├── public/
│   ├── package.json
│   ├── .env.example
│   └── Dockerfile
│
├── infrastructure/
├── benchmarks/
├── docs/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── .gitignore
├── LICENSE
└── README.md
```

*Proposed repository structure.*

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 22+
- PostgreSQL
- Redis (required for caching features)
- Git
- Docker and Docker Compose (optional)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd minify
```

### 2. Backend Setup

```bash
cd backend

python -m venv .venv
```

Activate the virtual environment.

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the environment variables and run database migrations:

```bash
alembic upgrade head
```

Start the development server:

```bash
uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

### 3. Frontend Setup

Open a separate terminal.

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

### 4. Docker Setup

Once the container configuration is implemented:

```bash
docker compose up --build
```

To stop the services:

```bash
docker compose down
```

The installation commands describe the planned development workflow and will be verified as the corresponding configuration files are implemented.

---

## Environment Variables

### Backend

Create `backend/.env` using the provided environment template.

```env
APP_NAME=Minify
APP_ENV=development
DEBUG=true

DATABASE_URL=postgresql://user:password@localhost:5432/minify
REDIS_URL=redis://localhost:6379/0

SECRET_KEY=replace_with_secure_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173

SHORT_CODE_LENGTH=7
CACHE_TTL_SECONDS=300
```

### Frontend

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Never commit actual credentials, database connection strings, API keys, or production secrets to version control.

---

## Engineering Design Decisions

### Short-Code Generation

Minify will use cryptographically secure random Base62 short codes.

The character set consists of:

```text
0123456789
ABCDEFGHIJKLMNOPQRSTUVWXYZ
abcdefghijklmnopqrstuvwxyz
```

A seven-character Base62 code provides approximately 3.52 trillion possible combinations.

Database-level uniqueness constraints and bounded retry logic will handle potential collisions.

### Caching Strategy

Minify will implement a cache-aside strategy using Redis.

- Cache frequently accessed URL mappings.
- Fall back to PostgreSQL on cache misses.
- Populate Redis following successful database lookups.
- Invalidate cached mappings when links are updated or deleted.
- Ensure cache expiration does not exceed link expiration.
- Continue serving valid database-backed redirects when Redis is unavailable.

PostgreSQL remains the authoritative source of truth.

### Redirection Strategy

HTTP `302 Found` redirects will be used by default to support mutable destinations, expiration, and click tracking.

### Analytics Strategy

Analytics processing will be separated from the critical redirection path to reduce response latency.

Aggregated reporting will be favored over unnecessary storage of identifiable visitor information.

### Error Handling

The API will implement consistent error responses and appropriate HTTP status codes.

| Status | Meaning |
|---|---|
| 200 | Successful request |
| 201 | Link created |
| 302 | URL redirection |
| 400 | Invalid request |
| 401 | Authentication required |
| 403 | Access forbidden |
| 404 | Resource not found |
| 409 | Alias conflict |
| 410 | Link expired |
| 422 | Validation error |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service temporarily unavailable |

---

## Testing

Minify aims to maintain a comprehensive automated testing strategy.

### Unit Tests

- Short-code generation
- URL validation
- Authentication logic
- Expiration handling
- Collision resolution

### Integration Tests

- Database operations
- URL creation and redirection
- Cache consistency
- Authentication and authorization
- Analytics recording

### End-to-End Tests

- Account registration
- URL shortening
- Dashboard interactions
- Link modification and deletion
- Production redirection

### Performance Tests

- Concurrent URL creation
- High-volume redirection
- Cache-hit and cache-miss latency
- Database throughput
- Sustained traffic handling

Planned test commands:

```bash
pytest -v
```

```bash
pytest --cov=app
```

Frontend:

```bash
npm run test
```

---

## Performance Benchmarks

Benchmarks will be published following implementation and controlled load testing.

| Metric | Target | Measured |
|---|---|---|
| Cached redirect latency, p95 | Under 50 ms | Pending |
| Uncached redirect latency, p95 | Under 150 ms | Pending |
| URL creation latency, p95 | Under 250 ms | Pending |
| Redirect throughput | 1,000 requests/sec | Pending |
| Cache hit ratio | Above 90% for a hot-link workload | Pending |
| Backend test coverage | Above 90% | Pending |

These figures are engineering targets, not verified performance results. Benchmark results will include hardware, infrastructure, workload, concurrency, and testing methodology.

---

## Security and Privacy

Minify will incorporate security throughout its architecture.

Planned measures include:

- Secure password hashing using Argon2id.
- Cryptographically secure short-code generation.
- Expiring authentication tokens.
- Resource-level ownership verification.
- Strict HTTP and HTTPS destination validation.
- Parameterized database queries.
- Configurable CORS policies.
- IP-based and account-based rate limiting.
- Malicious destination screening.
- Reserved route and alias protection.
- Protection against SSRF in server-side URL inspection.
- Data minimization and analytics retention policies.
- Dependency vulnerability scanning.
- Abuse reporting and link moderation.

Public URL shortening introduces inherent risks involving phishing, spam, and malicious redirects. Abuse prevention will be treated as a core engineering requirement before unrestricted public deployment.

---

## Deployment Architecture

```mermaid
flowchart LR
    U[Users] --> V[Vercel Frontend]
    U --> R[Render Backend]
    V --> R
    R --> N[Neon PostgreSQL]
    R --> C[Managed Redis]
    G[GitHub Actions] --> V
    G --> R
```

### Deployment Strategy

- Frontend deployed independently on Vercel.
- Backend deployed as a FastAPI service on Render.
- Persistent PostgreSQL database hosted on Neon.
- Managed Redis introduced during the performance phase.
- Environment-specific configuration.
- Automated CI/CD pipelines.
- Production health checks and smoke tests.
- Explicit production CORS configuration.
- Database migrations during controlled releases.

The public short-link domain must resolve to the backend redirect service or an appropriate reverse proxy.

---

## Development Roadmap

### Phase 01 — Foundation

- [ ] Repository initialization
- [ ] Backend project scaffolding
- [ ] Frontend project scaffolding
- [ ] Database configuration
- [ ] Environment management
- [ ] Initial CI pipeline

### Phase 02 — Core MVP

- [ ] URL validation
- [ ] Short-code generation
- [ ] URL persistence
- [ ] HTTP redirection
- [ ] Landing page
- [ ] Clipboard integration
- [ ] Core automated tests

### Phase 03 — Production Deployment

- [ ] PostgreSQL deployment
- [ ] Backend deployment
- [ ] Frontend deployment
- [ ] Production API integration
- [ ] Health checks
- [ ] End-to-end smoke testing

### Phase 04 — Link Management

- [ ] User authentication
- [ ] Personal dashboard
- [ ] Custom aliases
- [ ] Link editing and deletion
- [ ] Link expiration
- [ ] QR code generation

### Phase 05 — Analytics

- [ ] Click tracking
- [ ] Asynchronous event processing
- [ ] Geographic analytics
- [ ] Browser and device analytics
- [ ] Interactive analytics dashboard

### Phase 06 — Performance and Security

- [ ] Redis caching
- [ ] Database optimization
- [ ] Rate limiting
- [ ] Abuse prevention
- [ ] Security testing
- [ ] Load testing
- [ ] Performance benchmarking

### Phase 07 — Advanced Platform

- [ ] Public developer API
- [ ] API key management
- [ ] Custom domains
- [ ] Bulk URL shortening
- [ ] Team workspaces
- [ ] Webhook integrations
- [ ] Advanced observability

---

## Future Vision

Minify aims to evolve into a developer-first link infrastructure platform supporting both individual users and applications requiring reliable, programmable URL management.

Potential future capabilities include:

- Custom branded domains
- Developer SDKs
- Enterprise link management
- Dynamic destination routing
- Self-hosted deployments
- Distributed redirection infrastructure
- Regional edge caching
- Privacy-conscious analytics
- Organization-level access controls

---

## Contributing

Contributions, suggestions, and bug reports are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Implement and test your changes.
4. Commit your changes.
5. Push your branch.
6. Open a pull request.

```bash
git checkout -b feature/your-feature
git add .
git commit -m "feat: implement your feature"
git push origin feature/your-feature
```

Please ensure that contributions include appropriate tests, documentation, and adherence to the existing architectural conventions.

---

## License

The project license will be finalized before the first public release.

---

## Acknowledgements

Minify is built as an exploration of scalable backend engineering, modern web development, and production-oriented system design.

Inspired by the engineering challenges behind modern URL shortening and distributed link management services.

---

**MINIFY**

*Minimal links. Maximum utility.*
