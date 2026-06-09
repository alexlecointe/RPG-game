"""Unified infrastructure service — inspired by Polsia's polsia_infra.

Centralizes all infrastructure operations (Render, Neon, GitHub) behind
a single interface routed by company context. Skeleton key model:
one set of credentials, N companies.

Flow (mirrors Polsia):
  1. create_neon_database(slug)  -> Neon project + DB
  2. create_github_repo(slug)    -> GitHub repo from template
  3. create_render_service(slug) -> Render web service linked to repo
  4. provision_company(slug)     -> orchestrates 1+2+3
"""
from __future__ import annotations

import base64
import json
from typing import Optional

import httpx
import structlog

from app.core.config import get_settings

logger = structlog.get_logger()

RENDER_API = "https://api.render.com/v1"
NEON_API = "https://console.neon.tech/api/v2"
GITHUB_API = "https://api.github.com"

LANDING_TEMPLATE_FILES = {
    "package.json": json.dumps({
        "name": "rpg-landing",
        "version": "1.0.0",
        "scripts": {
            "start": "node server.js",
            "build": "echo 'no build'",
            "db:init": "node db/init.js",
        },
        "dependencies": {
            "express": "^4.21.0",
            "pg": "^8.13.0",
            "stripe": "^17.0.0",
            "cors": "^2.8.5",
        },
    }, indent=2),
    "server.js": """const express = require('express');
const cors = require('cors');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { Pool } = require('pg');

const app = express();

const pool = process.env.DATABASE_URL
  ? new Pool({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: false } })
  : null;

const PIXEL_ID = process.env.META_PIXEL_ID || '';
const CAPI_TOKEN = process.env.META_CAPI_TOKEN || '';
const COMPANY_SLUG = process.env.COMPANY_SLUG || '';
const BACKEND_WEBHOOK_URL = process.env.BACKEND_WEBHOOK_URL || '';

function pixelScript() {
  if (!PIXEL_ID) return '';
  return `<script>
!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}
(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init','${PIXEL_ID}');fbq('track','PageView');
</script>`;
}

function injectPixel(html) {
  if (!PIXEL_ID || !html) return html;
  const script = pixelScript();
  if (html.includes('</head>')) return html.replace('</head>', script + '</head>');
  if (html.includes('<body')) return html.replace('<body', script + '<body');
  return script + html;
}

async function sendMetaPurchase({ email, amount, currency, eventId }) {
  if (!PIXEL_ID || !CAPI_TOKEN) return;
  const hashedEmail = email
    ? crypto.createHash('sha256').update(email.trim().toLowerCase()).digest('hex')
    : undefined;
  const payload = {
    data: [{
      event_name: 'Purchase',
      event_time: Math.floor(Date.now() / 1000),
      event_id: String(eventId || Date.now()),
      action_source: 'website',
      user_data: hashedEmail ? { em: [hashedEmail] } : {},
      custom_data: {
        currency: (currency || 'eur').toUpperCase(),
        value: (amount || 0) / 100,
      },
    }],
  };
  try {
    const resp = await fetch(
      `https://graph.facebook.com/v20.0/${PIXEL_ID}/events?access_token=${CAPI_TOKEN}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }
    );
    if (!resp.ok) console.error('[CAPI] Error:', await resp.text());
    else console.log('[CAPI] Purchase event sent');
  } catch (err) {
    console.error('[CAPI] Failed:', err.message);
  }
}

async function forwardStripeEventToBackend(event) {
  if (!BACKEND_WEBHOOK_URL) return;
  try {
    const resp = await fetch(BACKEND_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    });
    if (!resp.ok) console.error('[WEBHOOK] Forward failed:', resp.status);
    else console.log('[WEBHOOK] Forwarded to backend');
  } catch (err) {
    console.error('[WEBHOOK] Forward error:', err.message);
  }
}

// Stripe webhook needs raw body — must be BEFORE express.json()
app.post('/api/webhook/stripe', express.raw({ type: 'application/json' }), async (req, res) => {
  const sig = req.headers['stripe-signature'];
  const endpointSecret = process.env.STRIPE_WEBHOOK_SECRET;
  const stripeKey = process.env.STRIPE_SECRET_KEY;
  if (!stripeKey) return res.status(503).json({ error: 'Stripe not configured' });

  const stripe = require('stripe')(stripeKey);
  let event;

  try {
    if (endpointSecret && sig) {
      event = stripe.webhooks.constructEvent(req.body, sig, endpointSecret);
    } else {
      event = JSON.parse(req.body.toString());
    }
  } catch (err) {
    console.error('Webhook signature verification failed:', err.message);
    return res.status(400).json({ error: 'Invalid signature' });
  }

  res.json({ received: true });

  if (event.type === 'checkout.session.completed' || event.type === 'payment_intent.succeeded') {
    const obj = event.data.object;
    const email = obj.customer_details?.email || obj.receipt_email || '';
    const amount = obj.amount_total || obj.amount || 0;
    const currency = obj.currency || 'eur';
    const paymentId = obj.payment_intent || obj.id || '';

    console.log(`[PAYMENT] ${email} paid ${amount/100} ${currency} (${paymentId})`);

    if (pool) {
      try {
        await pool.query(
          `INSERT INTO orders (customer_email, amount_cents, currency, stripe_payment_id, stripe_event_type, created_at)
           VALUES ($1, $2, $3, $4, $5, NOW())`,
          [email, amount, currency, paymentId, event.type]
        );
      } catch (err) {
        console.error('[DB] Failed to log order:', err.message);
      }
    }

    await sendMetaPurchase({ email, amount, currency, eventId: paymentId });
    await forwardStripeEventToBackend(event);
  }
});

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

app.get('/', (req, res) => {
  const indexPath = path.join(__dirname, 'public', 'index.html');
  try {
    const html = fs.readFileSync(indexPath, 'utf8');
    res.send(injectPixel(html));
  } catch {
    res.send(`<!DOCTYPE html><html><head><title>Coming Soon</title>${pixelScript()}</head><body><h1>Coming Soon</h1></body></html>`);
  }
});

app.get('/health', (req, res) => res.json({ status: 'ok', db: !!pool, pixel: !!PIXEL_ID }));

app.post('/api/email-signup', async (req, res) => {
  const { email } = req.body;
  if (!email) return res.status(400).json({ error: 'email required' });
  if (pool) {
    try {
      await pool.query(
        'INSERT INTO waitlist (email, created_at) VALUES ($1, NOW()) ON CONFLICT (email) DO NOTHING',
        [email]
      );
    } catch (err) { console.error('[DB] waitlist insert failed:', err.message); }
  }
  res.json({ status: 'subscribed', email });
});

app.post('/api/checkout', async (req, res) => {
  const stripeKey = process.env.STRIPE_SECRET_KEY;
  if (!stripeKey) return res.status(503).json({ error: 'Stripe not configured' });
  const stripe = require('stripe')(stripeKey);
  const { product, amount, success_url, cancel_url } = req.body;
  const session = await stripe.checkout.sessions.create({
    payment_method_types: ['card'],
    line_items: [{ price_data: { currency: 'eur', product_data: { name: product || 'Product' }, unit_amount: amount || 1000 }, quantity: 1 }],
    mode: 'payment',
    success_url: success_url || '/',
    cancel_url: cancel_url || '/',
    metadata: { company_slug: COMPANY_SLUG },
    payment_intent_data: { metadata: { company_slug: COMPANY_SLUG } },
  });
  res.json({ checkout_url: session.url });
});

app.get('/api/orders', async (req, res) => {
  if (!pool) return res.json({ orders: [], message: 'DB not configured' });
  try {
    const result = await pool.query('SELECT * FROM orders ORDER BY created_at DESC LIMIT 50');
    res.json({ orders: result.rows, count: result.rowCount });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/stats', async (req, res) => {
  if (!pool) return res.json({ message: 'DB not configured' });
  try {
    const orders = await pool.query('SELECT COUNT(*) as count, COALESCE(SUM(amount_cents),0) as total FROM orders');
    const waitlist = await pool.query('SELECT COUNT(*) as count FROM waitlist');
    res.json({
      total_orders: parseInt(orders.rows[0].count),
      total_revenue_cents: parseInt(orders.rows[0].total),
      waitlist_count: parseInt(waitlist.rows[0].count),
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, async () => {
  console.log(`Server running on port ${PORT}`);
  if (pool) {
    try {
      await pool.query('SELECT 1');
      console.log('[DB] Connected to Neon PostgreSQL');
    } catch (err) {
      console.error('[DB] Connection failed:', err.message);
    }
  }
});
""",
    "db/init.js": """const { Pool } = require('pg');
const pool = new Pool({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: false } });

async function init() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS waitlist (
      id SERIAL PRIMARY KEY,
      email VARCHAR(255) UNIQUE NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS orders (
      id SERIAL PRIMARY KEY,
      customer_email VARCHAR(255),
      amount_cents INTEGER NOT NULL,
      currency VARCHAR(10) DEFAULT 'eur',
      stripe_payment_id VARCHAR(255),
      stripe_event_type VARCHAR(100),
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);
  console.log('Tables created successfully');
  await pool.end();
}

init().catch(err => { console.error(err); process.exit(1); });
""",
    "public/index.html": "<!DOCTYPE html><html><head><title>Coming Soon</title></head><body><h1>Coming Soon</h1></body></html>",
    "render.yaml": """services:
  - type: web
    runtime: node
    buildCommand: npm install && node db/init.js
    startCommand: node server.js
    envVars:
      - key: NODE_ENV
        value: production
""",
    ".gitignore": "node_modules/\n.env\n",
    "README.md": "# Landing Page\n\nAuto-generated by RPG Agent Company.\n",
}


class InfraService:
    """Unified infra operations for all companies."""

    def __init__(self):
        self._settings = get_settings()

    def _headers(self, provider: str) -> dict:
        if provider == "render":
            return {"Authorization": f"Bearer {self._settings.render_api_key}", "Content-Type": "application/json"}
        if provider == "neon":
            return {"Authorization": f"Bearer {self._settings.neon_api_key}", "Content-Type": "application/json"}
        if provider == "github":
            return {"Authorization": f"token {self._settings.github_token}", "Accept": "application/vnd.github.v3+json"}
        return {}

    # ------------------------------------------------------------------
    # Neon PostgreSQL — one database per company
    # ------------------------------------------------------------------

    async def create_neon_database(self, company_slug: str) -> dict:
        """Create a Neon project + database for a company."""
        if not self._settings.neon_api_key:
            return {"provisioned": False, "error": "Neon API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{NEON_API}/projects",
                    headers=self._headers("neon"),
                    json={"project": {"name": f"rpg-{company_slug}"}},
                )
                resp.raise_for_status()
                data = resp.json()

            project = data.get("project", {})
            connection = data.get("connection_uris", [{}])[0].get("connection_uri", "")

            logger.info("neon_project_created", slug=company_slug, project_id=project.get("id"))
            return {
                "provisioned": True,
                "project_id": project.get("id"),
                "database_url": connection,
                "slug": company_slug,
            }
        except Exception as exc:
            logger.warning("neon_create_failed", slug=company_slug, error=str(exc))
            return {"provisioned": False, "error": str(exc)}

    async def get_neon_connection_uri(self, project_id: str) -> str:
        """Retrieve the connection URI for an existing Neon project."""
        if not self._settings.neon_api_key:
            return ""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{NEON_API}/projects/{project_id}/connection_uri",
                    headers=self._headers("neon"),
                    params={"role_name": "neondb_owner", "database_name": "neondb"},
                )
                resp.raise_for_status()
                return resp.json().get("uri", "")
        except Exception as exc:
            logger.warning("neon_connection_uri_failed", error=str(exc))
            return ""

    async def delete_neon_project(self, project_id: str) -> dict:
        if not self._settings.neon_api_key:
            return {"error": "Neon API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{NEON_API}/projects/{project_id}",
                    headers=self._headers("neon"),
                )
                resp.raise_for_status()
            return {"deleted": True}
        except Exception as exc:
            return {"deleted": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # GitHub — one repo per company
    # ------------------------------------------------------------------

    async def create_github_repo(self, company_slug: str) -> dict:
        """Create a GitHub repo and push the Express+Postgres template."""
        if not self._settings.github_token or not self._settings.github_org:
            return {"provisioned": False, "error": "GitHub token or org not configured"}

        repo_name = f"rpg-{company_slug}"
        org = self._settings.github_org

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{GITHUB_API}/orgs/{org}/repos",
                    headers=self._headers("github"),
                    json={
                        "name": repo_name,
                        "description": f"Landing page for {company_slug} — auto-generated",
                        "private": False,
                        "auto_init": True,
                    },
                )
                if resp.status_code == 422:
                    logger.info("github_repo_exists", repo=repo_name)
                else:
                    resp.raise_for_status()
                repo_data = resp.json()

            repo_url = repo_data.get("html_url", f"https://github.com/{org}/{repo_name}")
            clone_url = repo_data.get("clone_url", f"https://github.com/{org}/{repo_name}.git")

            await self._push_template_files(org, repo_name, company_slug)

            logger.info("github_repo_created", slug=company_slug, repo=repo_url)
            return {
                "provisioned": True,
                "repo_name": repo_name,
                "repo_url": repo_url,
                "clone_url": clone_url,
                "slug": company_slug,
            }
        except Exception as exc:
            logger.warning("github_create_failed", slug=company_slug, error=str(exc))
            return {"provisioned": False, "error": str(exc)}

    async def _push_template_files(self, org: str, repo_name: str, company_slug: str) -> None:
        """Push template files to the repo via GitHub Contents API."""
        headers = self._headers("github")

        async with httpx.AsyncClient(timeout=30) as client:
            for filepath, content in LANDING_TEMPLATE_FILES.items():
                file_content = content.replace("rpg-landing", f"rpg-{company_slug}")
                encoded = base64.b64encode(file_content.encode()).decode()
                await client.put(
                    f"{GITHUB_API}/repos/{org}/{repo_name}/contents/{filepath}",
                    headers=headers,
                    json={
                        "message": f"Add {filepath}",
                        "content": encoded,
                    },
                )

    async def push_code_to_repo(
        self, company_slug: str, filepath: str, content: str, message: str = "Update from agent"
    ) -> dict:
        """Push or update a single file in the company's repo."""
        if not self._settings.github_token or not self._settings.github_org:
            return {"error": "GitHub not configured"}

        org = self._settings.github_org
        repo_name = f"rpg-{company_slug}"
        headers = self._headers("github")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                existing = await client.get(
                    f"{GITHUB_API}/repos/{org}/{repo_name}/contents/{filepath}",
                    headers=headers,
                )
                sha = existing.json().get("sha") if existing.status_code == 200 else None

                payload: dict = {
                    "message": message,
                    "content": base64.b64encode(content.encode()).decode(),
                }
                if sha:
                    payload["sha"] = sha

                resp = await client.put(
                    f"{GITHUB_API}/repos/{org}/{repo_name}/contents/{filepath}",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()

            logger.info("github_file_pushed", slug=company_slug, file=filepath)
            return {"pushed": True, "file": filepath}
        except Exception as exc:
            logger.warning("github_push_failed", slug=company_slug, error=str(exc))
            return {"pushed": False, "error": str(exc)}

    async def delete_github_repo(self, company_slug: str) -> dict:
        if not self._settings.github_token or not self._settings.github_org:
            return {"error": "GitHub not configured"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{GITHUB_API}/repos/{self._settings.github_org}/rpg-{company_slug}",
                    headers=self._headers("github"),
                )
                resp.raise_for_status()
            return {"deleted": True}
        except Exception as exc:
            return {"deleted": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Render — one web service per company, linked to GitHub repo
    # ------------------------------------------------------------------

    async def _get_render_owner_id(self) -> str:
        """Fetch the Render owner (team/user) ID from the API if not configured."""
        if self._settings.render_owner_id:
            return self._settings.render_owner_id
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{RENDER_API}/owners?limit=1",
                    headers=self._headers("render"),
                )
                resp.raise_for_status()
                owners = resp.json()
                if owners:
                    return owners[0].get("owner", {}).get("id", "")
        except Exception as exc:
            logger.warning("render_owner_fetch_failed", error=str(exc))
        return ""

    async def create_render_service(
        self, company_slug: str, repo_url: str, database_url: str = ""
    ) -> dict:
        """Create a Render web service connected to the company's GitHub repo."""
        if not self._settings.render_api_key:
            return {"provisioned": False, "error": "Render API key not configured"}

        owner_id = await self._get_render_owner_id()
        if not owner_id:
            return {"provisioned": False, "error": "Could not determine Render owner ID"}

        env_vars = [
            {"key": "COMPANY_SLUG", "value": company_slug},
            {"key": "NODE_ENV", "value": "production"},
        ]
        if database_url:
            env_vars.append({"key": "DATABASE_URL", "value": database_url})
        if self._settings.stripe_secret_key:
            env_vars.append({"key": "STRIPE_SECRET_KEY", "value": self._settings.stripe_secret_key})
        if self._settings.stripe_webhook_secret:
            env_vars.append({"key": "STRIPE_WEBHOOK_SECRET", "value": self._settings.stripe_webhook_secret})
        if self._settings.meta_pixel_id:
            env_vars.append({"key": "META_PIXEL_ID", "value": self._settings.meta_pixel_id})
        if self._settings.meta_capi_token:
            env_vars.append({"key": "META_CAPI_TOKEN", "value": self._settings.meta_capi_token})
        if self._settings.backend_public_url:
            env_vars.append({
                "key": "BACKEND_WEBHOOK_URL",
                "value": f"{self._settings.backend_public_url.rstrip('/')}/api/v1/webhooks/stripe",
            })

        # Render API v1 requires serviceDetails wrapper and ownerId
        payload = {
            "type": "web_service",
            "name": f"rpg-{company_slug}",
            "ownerId": owner_id,
            "repo": repo_url,
            "autoDeploy": "yes",
            "branch": "main",
            "serviceDetails": {
                "runtime": "node",
                "plan": "free",
                "pullRequestPreviewsEnabled": "no",
                "envSpecificDetails": {
                    "buildCommand": "npm install && node db/init.js",
                    "startCommand": "node server.js",
                },
            },
            "envVars": env_vars,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{RENDER_API}/services",
                    headers=self._headers("render"),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            service = data.get("service", data)
            service_id = service.get("id", "")
            url = service.get("serviceDetails", {}).get("url", "")

            logger.info("render_service_created", slug=company_slug, service_id=service_id, url=url)
            return {
                "provisioned": True,
                "service_id": service_id,
                "url": f"https://{url}" if url and not url.startswith("http") else url,
                "slug": company_slug,
            }
        except Exception as exc:
            logger.warning("render_create_failed", slug=company_slug, error=str(exc))
            return {"provisioned": False, "error": str(exc)}

    async def trigger_deploy(self, service_id: str) -> dict:
        """Trigger a manual deploy on Render (after code push)."""
        if not self._settings.render_api_key:
            return {"error": "Render API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{RENDER_API}/services/{service_id}/deploys",
                    headers=self._headers("render"),
                    json={},
                )
                resp.raise_for_status()
                data = resp.json()
            return {"deploy_id": data.get("id", ""), "status": data.get("status", "")}
        except Exception as exc:
            return {"error": str(exc)}

    async def get_status(self, service_id: str) -> dict:
        if not self._settings.render_api_key:
            return {"error": "Render API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{RENDER_API}/services/{service_id}",
                    headers=self._headers("render"),
                )
                resp.raise_for_status()
                data = resp.json()
            return {
                "service_id": service_id,
                "name": data.get("name", ""),
                "status": data.get("suspended", "unknown"),
                "url": data.get("serviceDetails", {}).get("url", ""),
                "updated_at": data.get("updatedAt", ""),
            }
        except Exception as exc:
            return {"error": str(exc)}

    async def get_logs(self, service_id: str, lines: int = 100) -> str:
        if not self._settings.render_api_key:
            return "Render API key not configured"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{RENDER_API}/services/{service_id}/logs",
                    headers=self._headers("render"),
                    params={"limit": lines},
                )
                resp.raise_for_status()
                logs = resp.json()
            return "\n".join(
                f"[{entry.get('timestamp', '')}] {entry.get('message', '')}"
                for entry in logs
            )
        except Exception as exc:
            return f"Failed to fetch logs: {exc}"

    async def delete_render_service(self, service_id: str) -> dict:
        if not self._settings.render_api_key:
            return {"error": "Render API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{RENDER_API}/services/{service_id}",
                    headers=self._headers("render"),
                )
                resp.raise_for_status()
            return {"deleted": True}
        except Exception as exc:
            return {"deleted": False, "error": str(exc)}

    async def delete_all_infra(
        self,
        company_slug: str,
        service_id: str = "",
        neon_project_id: str = "",
    ) -> dict:
        """Tear down GitHub repo, Render service, and Neon project."""
        result: dict = {"company_slug": company_slug, "github": {}, "render": {}, "neon": {}}
        result["github"] = await self.delete_github_repo(company_slug)
        if service_id:
            result["render"] = await self.delete_render_service(service_id)
        else:
            result["render"] = {"deleted": False, "error": "service_id not provided"}
        if neon_project_id:
            result["neon"] = await self.delete_neon_project(neon_project_id)
        else:
            result["neon"] = {"deleted": False, "error": "neon_project_id not provided"}
        return result

    # ------------------------------------------------------------------
    # Full provisioning orchestration (like Polsia HEURE 0)
    # ------------------------------------------------------------------

    async def provision_company(self, company_slug: str) -> dict:
        """Full provisioning: Neon DB + GitHub repo + Render service.

        Called automatically when a company is created. Mirrors Polsia's
        create_instance() which provisions Render + Neon + GitHub atomically.
        """
        result: dict = {"company_slug": company_slug, "neon": {}, "github": {}, "render": {}}

        neon_result = await self.create_neon_database(company_slug)
        result["neon"] = neon_result
        # Neon is optional — landing page works without a DB
        database_url = neon_result.get("database_url", "")

        github_result = await self.create_github_repo(company_slug)
        result["github"] = github_result
        clone_url = github_result.get("clone_url", "")

        if clone_url:
            render_result = await self.create_render_service(
                company_slug, clone_url, database_url
            )
            result["render"] = render_result
        else:
            result["render"] = {"provisioned": False, "error": "No GitHub repo to link"}

        # Success = GitHub + Render provisioned (Neon is optional)
        provisioned = (
            github_result.get("provisioned", False)
            and result["render"].get("provisioned", False)
        )
        result["provisioned"] = provisioned
        result["url"] = result["render"].get("url", "")

        if provisioned:
            logger.info("company_fully_provisioned", slug=company_slug, url=result["url"])
        else:
            logger.warning("company_provision_incomplete", slug=company_slug, result=result)

        return result
