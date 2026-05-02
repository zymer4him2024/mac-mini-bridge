# Privacy Policy

**Effective date:** [FILL IN — e.g., 2026-05-15]
**Last updated:** [FILL IN]

---

> **Drafting notes (delete before publishing):**
>
> Items marked **[FILL IN]** require human input before the policy goes live:
> - Legal entity name and contact address (sole proprietor or company).
> - Contact email — should be a monitored address, not a personal account.
> - Effective date once the policy is published.
> - Korean Personal Information Protection Officer (name, title, contact) — required by PIPA for users in Korea.
>
> Defaults filled in from the codebase: model provider is self-hosted Ollama (no third-party LLM); GCP regions are Firestore `nam5` (North America multi-region) and Cloud Storage `us-central1`; default retention is 30 days from `DEFAULT_RETENTION_DAYS` in `firestore_users.py`.
>
> Translation: this draft is English. The published page must also exist in Korean and Brazilian Portuguese (the three v1 locales). Korean PIPA-specific clauses are flagged inline so the translator does not strip them.

---

## 1. Who we are

Shomery is a private notebook over your email inbox. You point Shomery at the senders you care about; it reads those emails, summarises each one, saves the summary, and lets you ask grounded questions about what's in your inbox.

This policy describes what information Shomery collects, why, where it goes, how long it stays, and the rights you have over it.

The data controller for the personal data described in this policy is **[FILL IN — legal entity name]**, **[FILL IN — registered address]**. You can reach us at **[FILL IN — contact email, e.g., privacy@shomery.com]**.

---

## 2. Scope

This policy covers your use of:

- The Shomery web app at `https://shomeryai.web.app` and any custom domain we operate under (such as a future `shomery.com`).
- Any Shomery service you connect via OAuth (Google sign-in, Google Drive).

It does **not** cover third-party services we link to (your Gmail, your Google Drive, your Telegram, your KakaoTalk, etc.) — those services are governed by their own privacy policies. Shomery only acts on data those services hand to us, with your permission.

---

## 3. Information we collect

### 3.1 Account information (from Google sign-in)

When you sign in with Google, we receive your Google profile basics: **email address, display name, profile photo URL, and Google account ID (UID)**. We store these so we can identify you across sessions, address you in the UI, and route your data to your account only.

### 3.2 Email content you ask us to watch

You explicitly tell Shomery which senders or domains to watch (in *Settings → Watched senders* or during onboarding). For each email that matches your watch list, Shomery reads:

- The email's metadata (sender, recipient list, subject, date).
- The email's body (text and HTML).
- Attached PDFs (and only PDFs — we do not read other attachment types).

We do not read emails from senders or domains outside your watch list.

### 3.3 Generated summaries and indexes

For each watched email, Shomery generates:

- A **markdown summary** (a structured rewrite of the email's key points, asks, and a suggested response).
- A **PDF rendering** of the original email and any attached PDFs (used to seed the summary).
- A **vector index** of the summary (embeddings used to ground question-answering).

These derived artifacts are stored alongside the email metadata in your account.

### 3.4 Settings and preferences

We store the configuration you set in the app: watched senders, notification channels (email digest, Telegram chat ID, etc.), preferred locale, and onboarding state.

### 3.5 Files in your Google Drive (when you connect Drive)

If you connect Google Drive, you choose a destination folder via Google's own folder picker. We then have the narrow `drive.file` permission, which lets us:

- **Create files** (markdown summaries) in the folder you chose.
- **Re-open files** that we created, or files you have explicitly handed to us via the picker.

We **cannot** list, read, or modify any other file in your Drive, and we never request that broader access. Our use of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

### 3.6 Operational and technical data

In the course of running the service we also collect:

- **Diagnostic logs** that help us see when the app fails (HTTP status codes, error messages, stack traces). Logs are scrubbed by `log_redaction.py` before retention so they do not include email contents or user-identifying tokens.
- **Error reports** sent to Sentry (our error monitoring provider) when the app encounters an unexpected exception. These include the URL, browser type, and a stack trace.
- **Approximate IP address** at sign-in time, used by Firebase Auth for fraud and abuse detection.

We do not run product analytics (Mixpanel, Amplitude, GA, etc.) in v1. We do not run advertising trackers.

---

## 4. Service providers we use

Shomery is built on a small set of providers. Each one processes data only on our instructions and only for the purposes described here.

| Provider | What they do for us | What they receive |
|---|---|---|
| **Google (Firebase Authentication)** | Verifies your Google sign-in. | Your Google profile basics; an approximate IP at sign-in. |
| **Google (Cloud Firestore)** | Stores your account data, settings, watched senders, summary metadata, and item records. | Everything in §3.1, §3.3 (metadata), and §3.4. Encrypted at rest by Google; encrypted in transit. |
| **Google (Cloud Storage for Firebase)** | Stores the actual `.md` summary files and the PDF renderings until you connect Drive. | The summary files in §3.3 (until they migrate to your Drive). |
| **Google (Drive API, when you connect Drive)** | Holds the markdown summaries inside the folder you choose. | Same as Cloud Storage above, but inside your Drive. |
| **Google (Gmail API)** | Lets the watcher read emails from your inbox. | Read-only access to messages from senders you have explicitly watch-listed. |
| **Sentry** | Captures unhandled exceptions in the app. | Error stack traces, URL, browser type. No email content. |
| **Telegram (when you enable it)** | Delivers a notification when a new summary lands. | The chat ID you supplied and the brief notification text. |

**Where summarisation and question-answering happen.** Shomery runs the language model that summarises your emails and answers your questions on its own infrastructure. We do **not** send your email contents to OpenAI, Anthropic, Google Gemini, or any other third-party model provider. No third party trains a model on your data, because no third-party model ever sees your data.

We do not sell your data. We do not share your data with advertising networks. We do not use your data to train any model that is shared across customers.

---

## 5. How we use your information

We use the information above to:

- Operate the core product: read watched emails, generate summaries, index them, surface them in your inbox view.
- Answer your scoped questions ("Ask this subject", "Ask this group") using only the corpus inside your account.
- Route notifications you have opted into.
- Diagnose errors and abuse.
- Respond to your requests (export, delete, support).

We do **not** use your data for advertising, profiling for ad targeting, cross-customer model training, or sale to third parties.

---

## 6. Where your data is stored and international transfers

Shomery uses Google Cloud infrastructure operated from data centres in the United States. Specifically: Firestore in the `nam5` multi-region (North America: `us-central1` and `us-east1`), and Cloud Storage in `us-central1`. If you are outside the United States, your data will be transferred to and processed in the United States.

Where applicable, transfers from the EEA, the United Kingdom, or Switzerland to the United States rely on the **Standard Contractual Clauses** (SCCs) Google has incorporated into its Data Processing Addendum, supplemented by the safeguards Google publishes for its cloud services.

For users in **South Korea**, this constitutes a transfer of personal information to a third country (the United States) under the Personal Information Protection Act (PIPA). The recipient is Google LLC; the purpose is hosting and computation as described in §4; the period is until you delete your account or the data ages out under §7. By signing in, you consent to this transfer; you may withdraw consent at any time by deleting your account in *Settings → Privacy & data*.

For users in **Brazil**, this transfer is conducted under the legal bases set out in Article 33 of the Lei Geral de Proteção de Dados (LGPD), specifically transfers to a country that provides an adequate level of protection or under contractual safeguards equivalent to those in the LGPD.

---

## 7. How long we keep your data

| Data type | Retention |
|---|---|
| Account profile (email, display name, UID) | Until you delete your account. |
| Settings and watched-sender list | Until you delete your account or remove individual entries. |
| Email metadata and generated summaries (Firestore + Storage) | Default **30 days** from the email's date, configurable per user up to a maximum of 365 days via `retentionDays` in your account config. After that, the retention sweeper removes the summary, the PDF, and the metadata. |
| Vector index entries | Same lifetime as the underlying summary. |
| Diagnostic logs | **30 days**, redacted (no email contents). |
| Sentry error reports | **90 days** (Sentry's default for our plan). |
| Auth records (Firebase Authentication) | Until you delete your account. |

When you delete your account (§9), every item in this table is removed for your account in a single cascade — there is no "soft delete" window.

---

## 8. Security

We protect your data with:

- **Transport encryption** (TLS) for everything in flight between your browser, Firebase, Google APIs, and the watcher.
- **At-rest encryption** for Firestore and Cloud Storage, provided by Google.
- **Envelope encryption** for the most sensitive fields, using Google Cloud KMS keys we control (`kms_envelope.py`).
- **Per-user isolation rules** in Firestore: every read and write is gated by `request.auth.uid == uid`. A signed-in user can only ever see their own folders, items, and configuration.
- **Log redaction** so diagnostic output never contains email contents or auth tokens.
- **Least-privileged scopes** (`drive.file`, not full `drive`).

No system is perfectly secure. If we ever discover a breach that materially affects you, we will notify you within the timeframe required by the laws that apply to you (in the EEA: 72 hours from awareness; in California, Korea, Brazil, etc., as locally required).

---

## 9. Your rights

You have rights over your data. Depending on where you live, the exact list and the exact deadlines differ. The mechanisms below cover all of them.

### 9.1 Universal rights, exposed in-app

In *Settings → Privacy & data* you can:

- **Export your data.** Downloads a single JSON file containing your account profile, your settings, every folder, every item, and every summary Shomery has stored for you.
- **Delete your account.** Removes your sign-in, your settings, every summary, the underlying Storage objects, and the Firebase Auth user. The deletion is final and immediate; we cannot recover deleted accounts.

### 9.2 Rights under the EU/UK GDPR (for users in the EEA, UK, and Switzerland)

You have the right to:

- **Access** the personal data we hold about you (covered by the in-app export).
- **Rectify** inaccurate data (you can edit your display name in your Google account; other identifiers are derived from Google).
- **Erase** your data (covered by in-app delete).
- **Restrict or object** to processing.
- **Data portability** (the in-app export is in JSON, machine-readable).
- **Withdraw consent** at any time.
- **Lodge a complaint** with your local supervisory authority. Find yours at https://edpb.europa.eu/about-edpb/about-edpb/members_en.

### 9.3 Rights under the California CCPA/CPRA

You have the right to know what personal information we collect, the right to delete it, the right to correct inaccurate information, the right to opt out of the "sale" or "sharing" of personal information (we do not sell or share your data), and the right not to be discriminated against for exercising these rights. You can exercise the access and deletion rights via the in-app controls in §9.1.

### 9.4 Rights under the Korean Personal Information Protection Act (PIPA) — 개인정보 보호법

You have the right to be informed about the collection and use of your personal information; the right to access, correct, and delete it; and the right to suspend its processing. You can exercise these rights via the in-app controls in §9.1, or by contacting us at **[FILL IN — contact email]**.

The **Personal Information Protection Officer** for Shomery is:

- Name: **[FILL IN]**
- Title: **[FILL IN]**
- Contact: **[FILL IN — email or phone]**

You may also lodge a complaint with the Personal Information Protection Commission (개인정보보호위원회) at https://www.pipc.go.kr or via the Personal Information Infringement Reporting Center at https://privacy.kisa.or.kr (118).

### 9.5 Rights under the Brazilian LGPD

You have the right to confirm the existence of processing, access your data, correct it, anonymise/block/delete unnecessary or excess data, port it, delete data processed with consent, be informed about the entities with whom we share data, and revoke consent. You can exercise these rights via the in-app controls in §9.1, or by contacting us at **[FILL IN — contact email]**. You may also lodge a complaint with the Autoridade Nacional de Proteção de Dados (ANPD) at https://www.gov.br/anpd.

### 9.6 Response time

We respond to verifiable requests within **30 days** (or sooner where a stricter deadline applies under the laws above). If we need longer, we will tell you why and when to expect a response.

---

## 10. Children

Shomery is not directed at children under **16** (or the local age of digital consent where higher), and we do not knowingly collect personal information from children. If you believe a child has signed up, contact us at **[FILL IN — contact email]** and we will delete the account.

---

## 11. Changes to this policy

If we change this policy in a way that materially affects how we handle your data, we will notify you in the app and update the **Effective date** at the top. Cosmetic changes (typo fixes, link updates, clarifications) will only update the **Last updated** date.

The previous versions of this policy are available on request at **[FILL IN — contact email]**.

---

## 12. Contact

For any privacy question, request, or concern:

**[FILL IN — legal entity name]**
**[FILL IN — registered address]**
**[FILL IN — contact email]**

For users in Korea, see also §9.4 for the Personal Information Protection Officer.
