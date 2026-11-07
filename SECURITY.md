# Callwise Security Architecture & Review Checklist 🛡️

Security and tenant isolation are foundational to Callwise. This document outlines the defense-in-depth security model implemented across all four phases of the project.

---

## 1. Security Architecture Summary

```text
+-----------------------------------------------------------------------------------+
|                              EDGE / INGRESS LAYER                                 |
|  - Caddy Reverse Proxy: TLS termination, HSTS, X-Content-Type-Options: nosniff    |
|  - CORS Regex: Strict origin filtering for dashboard and public widgets           |
|  - Global Emergency Kill Switch: Dynamic shutdown with fallback message-taking    |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                           AUTHENTICATION & SESSIONS                               |
|  - Passwords: Argon2id hashing with per-user salt                                 |
|  - Sessions: Cryptographic 64-character tokens, stored as SHA-256 in DB           |
|  - Cookies: HttpOnly, SameSite=Lax, Secure flags                                  |
|  - Double-Submit CSRF: Cryptographically validated per mutating state request    |
|  - Rate Limiting: 5 failed login attempts -> 15-minute progressive IP lockout     |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                        MULTI-TENANT ISOLATION LAYER                               |
|  - PostgreSQL Row Level Security (RLS) on all tenant tables                       |
|  - SET LOCAL app.current_business_id per database transaction                      |
|  - Role-Based Access Control (RBAC): Owner, Manager, Staff                        |
|  - Automated CI endpoint isolation scanning across all OpenAPI routes             |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                          AI & AGENT SAFETY GUARDRAILS                             |
|  - Hallucination Prevention: Below similarity cutoff -> declines speculation      |
|  - Prompt Injection Defense: Sanitization and strict system boundary fences       |
|  - SSRF Protection: Private IP and loopback blocking for knowledge scraping       |
|  - PII Redaction Filter: Credit cards, SSNs, and API keys scrubbed from logs     |
|  - Provider Circuit Breakers: Automatic failover on upstream failure              |
+-----------------------------------------------------------------------------------+
```

---

## 2. Threat Modeling & Mitigation Matrix

| Threat | Risk Level | Mitigation in Callwise |
|---|---|---|
| **Cross-Tenant Data Leakage** | Critical | PostgreSQL Row Level Security (RLS) enforces tenant boundaries at the database kernel level. Every request sets `app.current_business_id`. |
| **Credential Stuffing & Brute Force** | High | In-memory IP-based rate limiting enforces a 15-minute lockout after 5 consecutive failed attempts on `/api/auth/login`. |
| **Cross-Site Request Forgery (CSRF)** | High | Double-submit CSRF cookie pattern (`cw_csrf_token` cookie compared against `X-CSRF-Token` header using constant-time string comparison). |
| **Prompt Injection via Caller Input** | High | User turns are stripped of formatting exploits, enclosed within explicit quotation fences, and guided by system prompt instructions to prioritize tools over user claims. |
| **Server-Side Request Forgery (SSRF)** | High | Web knowledge scraper parses all URLs, resolves DNS, and strictly blocks private, loopback (`127.0.0.0/8`), Link-Local (`169.254.0.0/16`), and RFC-1918 addresses (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`). |
| **Unauthorized Booking Modification** | High | 6-character booking codes are stored as SHA-256 hashes. Rescheduling or cancelling requires caller verification against customer name and phone number with a 3-strike lockout. |
| **PII & Secret Leaks in Server Logs** | Medium | Custom `RedactionFilter` scrubs credit card numbers, Social Security Numbers, Bearer tokens, and passwords before formatting into JSON or text log streams. |
| **Telephony Flooding & Abuse** | Medium | Per-caller rate limiting restricts phone callers to 5 calls per hour. Nonsense and keyboard smash detectors flag abusive callers, block further turns, and alert the owner via email. |
| **Container Privilege Escalation** | Medium | Docker containers run under unprivileged, non-root users (`callwise:1001` in Python backend, `nextjs:1001` in web dashboard). |

---

## 3. Defense-in-Depth Verification Checklist

### Multi-Tenant Isolation
- [x] Every database table has a non-nullable `business_id` foreign key.
- [x] PostgreSQL Row Level Security (RLS) policies are active and enforced.
- [x] Automated test `test_openapi_automated_endpoint_isolation_scan` runs in CI, iterating over all endpoints to guarantee unauthenticated requests return 401 and cross-tenant requests return 403 or 404.

### Authentication & Passwords
- [x] Passwords are encrypted using Argon2id (`argon2-cffi`).
- [x] Passwords require at least 8 characters.
- [x] Sessions are stored in the `sessions` table using SHA-256 hashed tokens.
- [x] Cookies use `HttpOnly` and `SameSite=Lax`.

### API & Network Security
- [x] Security headers middleware injects `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, and `Referrer-Policy`.
- [x] Public widget endpoints allow iframe embedding (`X-Frame-Options` omitted); administrative dashboard enforces `X-Frame-Options: DENY`.
- [x] CORS middleware uses regex checking to allow valid local development ports while rejecting arbitrary external origins.

### Operational Controls
- [x] Emergency kill switch can be toggled via environment variable or instant CLI command (`callwise killswitch enable`).
- [x] Provider circuit breakers track failures and automatically route requests to fallback models when upstream providers fail.
- [x] Database backups are encrypted/compressed (`.sql.gz`) with restricted file permissions.

