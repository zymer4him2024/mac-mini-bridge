# Deployment Strategy — Two Seams, One Codebase

**Date:** 2026-04-29
**Status:** Active. Revisit when first enterprise lead presents a security review checklist.
**Owner:** Shawn

## The Tension

email2ppt today is a multi-tenant SaaS pilot running on a Mac mini. Firestore holds tenant metadata, leads, audit logs, and config. The marketing positioning leans on privacy and local AI (Ollama runs locally for every customer), but Firestore puts customer-derived data in Google Cloud — which will not survive a real enterprise security review for customers with GDPR Article 44 data residency requirements or "no email content in vendor cloud" policies.

The trap to avoid: build a full on-prem SKU now, before any enterprise customer has signed. We would be guessing at requirements that only a real security questionnaire can reveal. BYO-GCP-project might pass at one customer and be a dealbreaker at the next — only their checklist tells us which.

## The Decision

Architect behind **two seams now**, defer the deployment topology choice until a paying enterprise tells us what they actually need. Do not build a second SKU on speculation.

### Seam 1 — State Store

A single interface that hides whether tenant metadata, leads, users, audit, and alerts live in Firestore or local SQLite. Selected at startup via one config flag.

- SaaS topology → Firestore (today)
- On-prem topology → local SQLite (future, when triggered)

### Seam 2 — Blob Store

A single interface that hides whether generated artifacts (PDFs, PPTs, summaries, attachments) live on local disk or GCS. Selected by the same config flag.

- SaaS topology → local disk today, GCS when scale demands it
- On-prem topology → local disk, never leaves customer hardware

### Seam 3 (Later) — KMS

Same pattern for the encryption layer. Vendor-managed key for SaaS, customer-owned key for on-prem (Vault, AWS KMS, GCP KMS — whatever their security team specifies). Not built now; designed for when needed.

The `watcher.py` pipeline and Ollama integration are unchanged across topologies. Same code, two topologies:

- **SaaS:** vendor hardware + cloud backends (Firestore, future GCS)
- **On-prem:** customer hardware + local backends (SQLite, local disk)

## What To Do Now (Cheap, Pays Off Either Way)

The `firestore_alerts.py`, `firestore_users.py`, `firestore_leads.py`, and `firestore_audit.py` modules are already isolated. The single discipline that preserves the option to split later:

> **Do not import the Firestore SDK directly from `watcher.py` (or any pipeline module). All Firestore access goes through the `firestore_*.py` modules. No exceptions.**

This one rule keeps the future SaaS/on-prem split a days-long job instead of a months-long rewrite. It costs nothing today.

The same discipline applies as soon as we start writing artifact storage code — keep it behind a `blob_*.py` module from day one, even if the only implementation is local disk.

## What This Decision Defers (Intentionally)

We do **not** build, today:

- A second deployment bundle (installer, container image, signed update mechanism)
- A control-plane / data-plane separation in our infrastructure
- A license validation system
- Customer-facing telemetry minimization documentation
- BYOC Terraform modules

These are real work and will eat months. They wait for the trigger event below.

## Trigger Event

Build the on-prem SKU when **one paying enterprise** has signed and shared their security review checklist. Their requirements — not our guesses — define:

- Whether BYO-GCP-project is acceptable, or full air-gap is required
- Whether they accept vendor-issued license JWTs or demand offline-only operation
- Which KMS they expect us to integrate with
- What audit log format and retention policy they need
- What the SLA is for security patches and vulnerability disclosure

Until that checklist exists, anything we build is speculation.

## Roadmap Risk

Shipping all three SKUs (SaaS, BYOC, on-prem) simultaneously is what kills small teams. The two-seams discipline buys optionality without committing to that. When the first enterprise lands, we pick **one** topology to harden — likely the simplest one that closes their deal — and the other follows when a second customer asks for it.

## Future Compliance Destination

Full security compliance is the eventual destination. Targets to keep in mind, not work to start:

- GDPR Article 44 (data residency, international transfers)
- SOC 2 Type II (likely first formal audit)
- A Data Processing Agreement template that distinguishes SaaS-tier from on-prem-tier processing
- Documented data classification (data-plane vs. control-plane fields)

These are not today's work. They are the destination this strategy keeps reachable.

## Review Cadence

Revisit this document when any of the following happens:

1. First enterprise prospect requests on-prem deployment
2. A SaaS customer's storage exceeds local disk capacity (forcing the GCS swap)
3. Ollama is replaced or augmented with a remote inference provider (would break the "local AI for everyone" assumption)
4. A regulator or auditor requires changes to where Firestore data resides
