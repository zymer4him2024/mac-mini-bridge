# Landing Page Copy — [PRODUCT NAME]

Two parallel versions. Pick **A** as your default homepage. Use **B** as a separate `/privacy` or `/security` landing page you link to from outbound emails to security buyers.

---

## VERSION A — Sales-led (default homepage)

### Hero

**H1.** Every inbound email, tracked, summarized, deck-ready.

**Sub.** [PRODUCT NAME] turns your inbox into a sales pipeline. New leads are summarized, scored, and added to your tracker the moment they hit your inbox — and your weekly report writes itself.

**Primary CTA.** Book a 15-minute demo
**Secondary CTA.** See it work in 90 seconds *(links to a Loom)*

**Hero visual.** Product screenshot: a Gmail thread on the left, a clean lead card with summary + status on the right, an arrow between them. Soft shadow, off-white background.

---

### Trust strip *(below hero)*

> Trusted by sales teams at *[Logo]* · *[Logo]* · *[Logo]* · *[Logo]* · *[Logo]*

*(Use 5 placeholder grey rectangles until you have real logos. Don't fake them.)*

---

### Section 1 — The problem (2 sentences, big text)

**The reality:** Your team gets 40 inbound leads a week. By Friday, half of them are buried under reply threads and nobody's updated the CRM. The leads that don't reply twice get forgotten.

---

### Section 2 — Three feature blocks

**Block 1 — Summarize, automatically**
*Headline:* Read once, never again.
*Body:* Every relevant email gets a 200-word executive summary the moment it arrives — sender intent, key requirements, budget signals, and priority. Your reps stop re-reading threads.

**Block 2 — Track, without prompting**
*Headline:* Your CRM, finally up to date.
*Body:* Each lead is logged in a master tracker with status, owner, and last-touched date. Duplicates are auto-merged. No one has to "remember to update Salesforce."

**Block 3 — Report, without writing**
*Headline:* Monday-morning decks, written for you.
*Body:* Every week, [PRODUCT NAME] generates a slide deck and Excel summary of new opportunities, conversion metrics, and pipeline health. Walk into your Monday meeting ready.

*(Each block: icon, headline, 2-line body, screenshot.)*

---

### Section 3 — How it works (3 steps)

1. **Connect your inbox.** Gmail, Outlook, or shared sales@ — 90 seconds, no IT ticket needed.
2. **We watch for new leads.** Each one is summarized, classified, and added to your tracker.
3. **You get a weekly report.** Slide deck and spreadsheet, in your inbox every Monday at 8am.

---

### Section 4 — Social proof block

> "We were losing 1 in 4 leads to follow-up gaps. With [PRODUCT NAME] running on our shared sales@ inbox, that dropped to under 1 in 20. The Monday deck alone saved my Sales Ops Lead a full day a week."
>
> — *[Name]*, *[Title]* at *[Company]*

*(Replace with real quote within 30 days of first paying customer. Until then, leave the section out — fake quotes are worse than no quote.)*

---

### Section 5 — Pricing teaser

**Starter** — `$[X]/mo` · for teams of 1–5
**Team** — `$[X]/mo` · for teams of 6–25
**Enterprise** — Custom · for teams of 25+ or anyone with a security review

**CTA.** See full pricing → *(links to /pricing)*

---

### Section 6 — FAQ (top 4)

- *Does this work with my existing CRM?* Yes — Salesforce, HubSpot, Pipedrive, and Notion are supported. The tracker is the source of truth; we sync to your CRM.
- *What about emails that aren't sales leads?* [PRODUCT NAME] only acts on emails it classifies as inbound interest. Everything else stays untouched.
- *How accurate is the AI?* In our pilot, 94% of summaries needed zero edits. Ambiguous emails are flagged for human review instead of guessed at.
- *Where does my data go?* The AI runs locally — your email content never leaves your perimeter. *(See the [security page] for details.)*

---

### Footer CTA

**H2.** Stop losing leads to your inbox.
**Sub.** Most teams recover the cost of [PRODUCT NAME] in the first week.
**Primary CTA.** Book a 15-minute demo

---

## VERSION B — Privacy-led (security landing page at /privacy or /security)

### Hero

**H1.** Your inbox is yours. The AI runs locally.

**Sub.** [PRODUCT NAME] is the only inbound-lead automation platform where customer email content never leaves your hardware. The AI model runs on-device. No third-party LLM. No data exhaust. No surprises in your next security review.

**Primary CTA.** Request a security review packet
**Secondary CTA.** See the architecture *(links to /architecture)*

**Hero visual.** Diagram: customer hardware on the left (with a lock icon), inbox flowing into a local AI box, output flowing back to customer storage. No cloud. Single deep-blue accent.

---

### Section 1 — Why this matters (the problem framed for security buyers)

Most "AI inbox" tools send your email content to a third-party LLM provider. Your customer correspondence — names, contracts, pricing, roadmaps — leaves your perimeter and lands in someone else's training pipeline (or at minimum, their logs).

For regulated teams, this is not acceptable. GDPR Article 44 restricts international data transfers. SOC 2 Type II auditors flag third-party AI vendors. Your customers' MSAs explicitly forbid it.

[PRODUCT NAME] was built for that constraint.

---

### Section 2 — How we're different (three blocks)

**Block 1 — Local AI, by default**
Every customer runs their own instance of an open-source LLM (Ollama-based) on their own hardware. No call leaves the box. The same code path is used by every customer — no "enterprise mode" you have to negotiate for.

**Block 2 — Two deployment topologies, one codebase**
Choose SaaS (we host the orchestration layer; AI still runs on your edge) or fully on-premise (everything on your hardware, including state and storage). Same product. Your security team picks the topology.

**Block 3 — Designed for the audit**
Audit logs are append-only and exportable. Data classification is documented (control-plane vs. data-plane fields). DPA template available. SOC 2 Type II is on the roadmap.

---

### Section 3 — Architecture at a glance

*(Embed the seam diagram here. State store + blob store + KMS, each abstracted behind an interface. Two deployment topologies, one codebase.)*

**Topology 1 — SaaS:** Vendor-managed orchestration. Customer-managed AI inference (always local). Eligible for most cloud-permitted environments.

**Topology 2 — On-premise:** Customer hardware end-to-end. Air-gap compatible. Eligible for the most restrictive environments (defense, regulated finance, healthcare with PHI in the inbox).

---

### Section 4 — What we will not do

- We will not send your email content to a third-party LLM API.
- We will not retain customer data for model training. Ever.
- We will not deploy on any infrastructure your security team has not approved.
- We will not silently change deployment topologies after a contract is signed.

---

### Section 5 — Compliance roadmap

| Status | Standard |
|---|---|
| **Now** | DPA template available. Audit logs exportable. Local-AI architecture. |
| **In progress** | SOC 2 Type II readiness assessment. |
| **On request** | GDPR Article 44 attestation pack. Customer-specific security review checklist. |

*Honest framing: full SOC 2 Type II is the destination, not today's reality. Inviting the conversation rather than overclaiming.*

---

### Section 6 — Footer CTA

**H2.** Bring [PRODUCT NAME] to a security review with confidence.
**Sub.** We've engineered for the questions your team is going to ask.
**Primary CTA.** Request a security review packet

---

## Notes for the designer

- Both pages use the same component library — only the copy differs.
- Version A leads with product screenshots. Version B leads with architecture diagrams.
- A → B internal link belongs in the footer of Version A: *"Worried about where your email data goes? Read our security page."*
- B → A internal link belongs in the footer of Version B: *"Looking for the product overview? Start here."*
