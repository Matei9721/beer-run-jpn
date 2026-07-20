# Architectural Decision Records: 005-add-signup-api

## ADR-001: Extract Auth-Facing HTTP Routes From `main.py`

- **Date:** 2026-07-19
- **Status:** Accepted
- **Context:** The completed signup implementation left `main.py` at 349 lines and mixed authentication HTTP concerns with application composition, trip routes, and image handling. The specification's Integration Points originally placed `POST /api/signup` beside `/token` and `/api/me` in `main.py`. The user explicitly requested a cleanup after reviewing that result.
- **Decision:** Move `/token`, `/api/signup`, `/api/me`, signup validation constants, duplicate-error classification, and signup-specific request-error sanitization into a single root-level `auth_routes.py` FastAPI router. Keep startup configuration/readiness checks and router registration in `main.py`. Keep JWT, password, and signup-code primitives in `auth.py`.
- **Rationale:** This creates one direct module boundary around related HTTP behavior, reduces `main.py` from 349 to 223 lines, and avoids introducing a service layer or broader abstraction into the compact application.
- **Consequences:** Public paths, request/response models, status codes, authentication behavior, persistence, and deployment commands remain unchanged. Future auth HTTP changes belong in `auth_routes.py`; application startup and non-auth routes remain in `main.py`.
