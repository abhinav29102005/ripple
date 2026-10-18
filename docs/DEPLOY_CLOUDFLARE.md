# Deploying Ripple Front End to Cloudflare Workers (Static Assets)

This guide documents how to deploy the static React front end to Cloudflare using Git integration via the Cloudflare Dashboard.

---

## 1. Dashboard Git Integration Setup

1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **Workers & Pages** > **Create application** > **Pages** or **Workers Static Assets**.
3. Select **Connect to Git** and choose the `ripple` repository.
4. Select the target production branch (e.g., `main` or `ui-react`).

---

## 2. Build Configuration Settings

Configure the build settings in the Cloudflare deployment modal:

| Field | Configuration Value | Notes |
|---|---|---|
| **Framework preset** | `Vite` (or `None`) | Standard client build |
| **Root directory** | `web` | Directs Cloudflare to the React project directory |
| **Build command** | `npm ci && npm run build` | Clean install and compile to `dist/` |
| **Build output directory** | `dist` | Contains compiled client bundles and assets |

---

## 3. Environment Variables

Under **Settings** > **Environment variables** (Production), add:

| Variable | Example Value | Description |
|---|---|---|
| `VITE_API_BASE` | `https://api.your-domain.sslip.io` | Absolute URL of the backend API deployed on AWS (no trailing slash). |
| `NODE_VERSION` | `20` | Supported LTS Node.js runtime for build execution. |

> **Security Note:** The build process enforces a build-time security assertion that fails if any environment variable prefixed with `VITE_` contains `KEY`, `SECRET`, `TOKEN`, or `PASSWORD`.

---

## 4. Single-Page Application (SPA) Routing

Single-page routing is configured in `web/wrangler.jsonc` via the Workers Static Assets `not_found_handling` directive:

```jsonc
{
  "name": "ripple-web",
  "compatibility_date": "2024-09-23",
  "assets": {
    "directory": "./dist",
    "not_found_handling": "single-page-application"
  }
}
```

This ensures that any client-side route requests automatically resolve to `/index.html` with HTTP 200 rather than throwing a 404.
