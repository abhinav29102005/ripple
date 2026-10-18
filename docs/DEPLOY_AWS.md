# Deploying Ripple API to AWS (EC2 + Caddy + Docker Compose)

This guide documents deploying the Ripple backend API to an AWS EC2 instance behind Caddy with automatic TLS certificates, strict CORS, and reverse-proxy rate limiting.

---

## 1. Allocate an Elastic IP & Derive `sslip.io` Hostname

1. In the AWS Management Console, navigate to **EC2** > **Network & Security** > **Elastic IPs**.
2. Click **Allocate Elastic IP address** and assign it to your target EC2 instance.
3. Note the allocated Public IPv4 address (e.g. `54.252.120.45`).
4. Derive your free, auto-resolving SSL-ready hostname by converting the IPv4 dots to dashes:
   $$\text{IP: } 54.252.120.45 \longrightarrow \text{Hostname: } \mathbf{54-252-120-45.sslip.io}$$
   *`sslip.io` is a public wildcard DNS service that resolves `54-252-120-45.sslip.io` directly to `54.252.120.45` without requiring manual DNS configuration.*

---

## 2. Security Group Configuration

Configure your EC2 Security Group with strictly restricted inbound rules:

| Type | Port Range | Protocol | Source | Purpose |
|---|---|---|---|---|
| **HTTPS** | 443 | TCP | `0.0.0.0/0` | Public encrypted API traffic |
| **HTTP** | 80 | TCP | `0.0.0.0/0` | Let's Encrypt ACME challenge / HTTP to HTTPS redirect |
| **SSH** | 22 | TCP | `Your IP` | Server administrative management |

> **CRITICAL SECURITY REQUIREMENT:**
> Ports `8000` (FastAPI), `6379`/`6380` (FalkorDB Redis protocol), and `3000` (FalkorDB Browser) **must never be published** to the public internet. In `docker-compose.prod.yml`, FalkorDB and the FastAPI app run inside the private Docker network; only Caddy binds to host ports 80 and 443.

---

## 3. Production Environment Configuration (`.env`)

On the EC2 instance, clone the repository and configure `.env`:

```bash
# Domain & Proxy Configuration
SITE_ADDRESS=54-252-120-45.sslip.io
TRUST_PROXY=1

# Strict CORS: Comma-separated list of allowed origins (e.g. your Cloudflare Workers URL)
CORS_ORIGINS=https://ripple-web.workers.dev,https://ripple-web.pages.dev

# Production Hardening & Public Demo Mode
PUBLIC_MODE=1
LLM_MODE=off
```

### Environment Variable Roles:
- **`SITE_ADDRESS`**: Instructs Caddy which hostname to obtain automated Let's Encrypt / ZeroSSL certificates for.
- **`TRUST_PROXY=1`**: Instructs the FastAPI rate limiter to determine the client IP from the last `X-Forwarded-For` address added by Caddy rather than Caddy's internal docker bridge socket IP.
- **`CORS_ORIGINS`**: Enforces strict origin matching in `CORSMiddleware`. Wildcard `*` is strictly forbidden.
- **`PUBLIC_MODE=1`**: Activates the 10 req/min rate limiter and disables destructive endpoints (`/api/reset`, `/api/chaos/run`, `/api/tenants/{tenant}/load-demo`).
- **`LLM_MODE=off`**: Ensures deterministic analyst execution using FalkorDB graph algorithms without external model API dependencies.

---

## 4. Launch Production Stack

Start the production containers:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Monitor Caddy TLS certificate acquisition:

```bash
docker compose -f docker-compose.prod.yml logs -f caddy
```

---

## 5. Verify Deployment via HTTPS Health Check

Verify end-to-end TLS and API health using `curl`:

```bash
curl -i https://54-252-120-45.sslip.io/api/health
```

Expected response:
```http
HTTP/2 200
content-type: application/json
server: Caddy
strict-transport-security: max-age=31536000; includeSubDomains; preload
x-content-type-options: nosniff
x-frame-options: DENY

{"status":"ok","graphs":["knowledge","coord","tenant_cardio","tenant_onco"],"llm_mode":"off"}
```

---

## 6. Fallback: Certificate Issuance on `sslip.io`

Because `sslip.io` is a shared public domain, Let's Encrypt occasionally enforces global rate limits on new certificate requests for the root zone. If Caddy logs show an ACME rate-limit failure for `*.sslip.io`, use one of the following fallbacks:

### Fallback A: Custom Domain with Direct A-Record (Recommended)
1. In your domain registrar (e.g. Cloudflare, Route53, Namecheap), create a DNS `A` record:
   `api.yourdomain.com -> 54.252.120.45`
2. Update `.env`:
   `SITE_ADDRESS=api.yourdomain.com`
3. Restart Caddy (`docker compose -f docker-compose.prod.yml restart caddy`). Caddy will issue a fresh TLS certificate for your custom domain.

### Fallback B: Cloudflare Tunnel (`cloudflared`)
1. Create a Cloudflare Tunnel in the Cloudflare Zero Trust dashboard.
2. Run `cloudflared` on the EC2 instance routing traffic directly to `http://localhost:8000`.
3. Cloudflare manages SSL termination at the edge; no inbound firewall ports (80/443) are required on EC2.
