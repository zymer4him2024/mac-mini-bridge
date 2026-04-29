# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in email2ppt, please
**do not file a public issue**. Email **security@email2ppt.example** with:

- A description of the vulnerability and its potential impact.
- Steps to reproduce or proof-of-concept.
- Your name and affiliation (optional).

We aim to acknowledge within 2 business days and provide an initial assessment
within 7 days. Coordinated disclosure is preferred; we will agree on a public
disclosure date together once a fix is available.

## Supported Versions

email2ppt is delivered as a managed service. Only the version currently
deployed at `email2ppt.web.app` (portal) and the Mac Mini / Cloud Run workers
on the corresponding `main` branch are supported. We do not maintain
back-ports.

## Threat Model (Summary)

We harden against:

1. **External attackers** — stolen OAuth tokens, phishing of the consent
   screen, abuse of the Cloud Function endpoints, IDOR across user
   documents.
2. **Malicious tenants** — multi-tenant isolation between paying customers;
   no customer can read or write another customer's data via the client
   SDK or the public API.
3. **Insider / operator abuse** — service-account access is logged via the
   audit collection; sensitive secrets are wrapped with KMS (roadmap).
4. **Supply chain** — dependency pinning, secret scanning (gitleaks),
   static analysis (bandit, ruff), Dependabot.

Out of scope: the local LLM (Ollama) runs offline on the worker host;
prompt-injection from email content can shape the LLM's output but cannot
exfiltrate data or escalate privileges.

## Encryption Posture

| Surface | Today | Roadmap |
| --- | --- | --- |
| TLS in transit | All traffic to Google APIs, Telegram, and Firestore over TLS 1.2+. | — |
| Firestore at rest | Google-managed encryption (AES-256). | App-level KMS envelope encryption for `users/{uid}/secrets/*` and `users/{uid}.customerBot.token` (Phase B). |
| OAuth refresh tokens | Stored server-side only (never sent to browser); written by the `gmailOauthCallback` Cloud Function. | KMS-wrapped (Phase B). |
| Telegram bot tokens | Currently written by the client SDK; moving behind a `setCustomerBot` Cloud Function (Phase A). | KMS-wrapped (Phase B). |
| Local credential files (`gmail_token.json`, `gmail_credentials.json`) | `chmod 0600`, owner-only. | Migrated off local disk on Cloud Run tenants (Phase C). |
| Local email content (`~/email-pdfs/{uid}/`, `~/email-digests/{uid}/`) | Plaintext on the worker host's encrypted volume (FileVault on Mac Mini). | Per-user encryption + retention sweep (Phase B). |

## Compliance

We are working toward GDPR alignment, SOC 2 Type II, and ISO 27001
readiness. HIPAA-aligned controls are tracked but no Business Associate
Agreement is offered today.

A live control matrix and the Data Processing Addendum template are
available on request.

## Cryptography

We rely on:

- Google Cloud Firestore default encryption.
- Firebase Auth tokens (signed by Google).
- TLS via `requests`, `httpx`, and `firebase-admin` defaults.

We do not roll our own crypto.
