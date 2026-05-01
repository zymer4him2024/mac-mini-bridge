# FAQ + Objection Handler — [PRODUCT NAME]

For sales calls, demos, website FAQ section, and your own confidence in the pitch. Each answer is written for two contexts: a **short verbal** version for live calls, and a **long written** version for follow-up email or website.

Categorized by **Pricing**, **Security & Privacy**, **AI quality**, **Integration**, **Deployment**, and **Support**.

---

## Pricing

### 1. Why does it cost what it costs?

**Short:** It's priced to recover its cost in the first week for most teams. The savings come from leads not dropped and time not spent re-reading email threads.

**Long:** [PRODUCT NAME] is priced per inbox per month. The pricing assumes a sales rep is worth at least [$50/hour] to your business. If [PRODUCT NAME] saves them 5 hours a week — which is the average in our pilot — the tool pays for itself many times over. We deliberately did not price per email volume because that creates the wrong incentive (less product use to save money).

---

### 2. Do you offer a free trial?

**Short:** Yes — 14 days, no credit card. We connect to a single inbox and you see a real Monday report by the end of week 1.

**Long:** Trials are 14 days on a single inbox. We use your real inbound traffic, so by day 4 you have meaningful summaries to evaluate quality. We do not require a credit card upfront. If you choose to continue, we keep your historical data — it does not get reset.

---

### 3. What's the cancellation policy?

**Short:** Monthly billing, cancel anytime. Annual gets a 20% discount.

**Long:** Month-to-month plans cancel with one click in the dashboard. Annual contracts get a 20% discount and renew automatically; you can cancel auto-renew at any point during the term. Your data is exportable at any time, no support ticket needed.

---

## Security & Privacy

### 4. Where does my email content go?

**Short:** Nowhere. The AI runs on your hardware (or on dedicated hardware we run for you). Your email content never reaches a third-party LLM.

**Long:** [PRODUCT NAME] uses an open-source language model (Ollama-based) that runs locally — either on your machine, on dedicated hardware in your cloud, or on hardware we manage in the SaaS topology. There is no API call to OpenAI, Anthropic, Google, or any other third-party LLM provider. Your email content does not leave the deployment boundary. We can demonstrate this in a network packet capture during a security review.

---

### 5. Are you SOC 2 / GDPR / HIPAA compliant?

**Short:** SOC 2 Type II is in progress, not certified yet. The architecture is GDPR-friendly. HIPAA isn't on today's roadmap.

**Long:** Honest answer: SOC 2 Type II is a destination, not a current state. We are in pre-audit readiness. The architecture is designed to pass — local AI, two-seam deployment, append-only audit logs, exportable data — but the certification work takes 12+ months and we are not pretending to have finished it. For GDPR Article 44 specifically, the on-premise topology fully resolves international transfer concerns. HIPAA-grade BAAs are not a 2026 commitment; please ask if it becomes a buying requirement.

---

### 6. What happens to my data if I cancel?

**Short:** You can export everything at any time. We delete it 30 days after cancellation. Audit logs of the deletion are exportable.

**Long:** Customer data is fully exportable as CSV/JSON via the dashboard or API at any point during the contract. On cancellation, you have a 30-day window to export. After that window, we permanently delete all customer data (state store + blob store + audit logs). The deletion is logged and the deletion log can be exported and stored on your side as proof.

---

### 7. Can I host this on-premise?

**Short:** Yes — it's the same product, configured to run on your hardware. Pricing is different.

**Long:** [PRODUCT NAME] was architected from day one with two deployment topologies in mind: SaaS and on-premise. The codebase has two clean abstraction seams (state store and blob store) that select between cloud and local backends via a single config flag. Same code, two topologies. On-premise pricing reflects the reduced infrastructure burden on us and the increased support obligation; please request a quote.

---

## AI quality

### 8. How accurate is the AI?

**Short:** In our pilot, 94% of summaries needed zero edits. Ambiguous emails get flagged for human review instead of guessed at.

**Long:** Our published number is "94% summary accuracy at first pass," based on a sample of 500 inbound emails across 4 pilot customers, scored by the customers themselves. The remaining 6% get flagged with a "Needs Human Review" tag rather than producing a confident-but-wrong summary. We are deliberately conservative — we'd rather under-promise on AI than ship a system that sounds confident and is wrong 1 in 10 times.

---

### 9. What if the AI gets it wrong?

**Short:** Every summary shows the source thread, and reps can correct it in two clicks. Corrections improve future accuracy for that customer.

**Long:** Each lead card links back to the original email thread, so a rep can verify the summary in seconds. Corrections are stored as feedback signals — over time, the model adapts to your domain language, deal sizes, and priority signals. We never train a global model on your corrections; the adaptation stays within your tenant.

---

### 10. Why a local model? Aren't cloud models better?

**Short:** For inbox triage, the gap is small and shrinking. Privacy is the bigger constraint for our customers.

**Long:** Frontier cloud models (GPT-5, Claude Opus 4.6) are still better at the very hardest reasoning tasks. For email summarization and classification, modern open-source models (Llama, Qwen, Gemma at 8B–70B parameters) score within a few percentage points of frontier models — well inside the noise floor for this task. The privacy and cost predictability advantages dominate. If a customer specifically requests a frontier-model option, we are open to building a "use your own API key" path; today the demand is overwhelmingly for the local default.

---

## Integration

### 11. What inboxes does it support?

**Short:** Gmail, Google Workspace, Outlook, Microsoft 365, and any IMAP inbox.

**Long:** Native connectors for Gmail/Google Workspace and Outlook/Microsoft 365 via OAuth — no IMAP password sharing required. Generic IMAP works for self-hosted mail servers. Setup is 90 seconds for native connectors; ~5 minutes for IMAP.

---

### 12. Does it sync to my CRM?

**Short:** Yes — Salesforce, HubSpot, and Pipedrive natively. Notion and Airtable via Zapier.

**Long:** [PRODUCT NAME] is the source of truth for the inbound lead pipeline; we sync downstream into your CRM rather than treating the CRM as primary. Native two-way sync with Salesforce, HubSpot, and Pipedrive. Zapier integration covers Notion, Airtable, monday.com, and Smartsheet. Webhook output is available for custom destinations.

---

### 13. Can my team override what [PRODUCT NAME] does?

**Short:** Yes — every action is reversible, and you can configure rules per inbox.

**Long:** Every automated action (summary, status change, deck generation) is logged and reversible from the dashboard. Per-inbox rules can specify which senders to ignore, which keywords escalate priority, and how aggressively to auto-classify. The default settings work out of the box; teams that want fine-grained control have it.

---

## Deployment

### 14. How long does setup take?

**Short:** 90 seconds for an inbox connection, 1 day to feel confident, 1 week to have your first Monday deck.

**Long:** OAuth-connecting your first inbox is a 90-second flow. By the end of day 1, you'll have ~20 real summaries to inspect. By the end of week 1, you'll receive your first auto-generated weekly deck. We do not require an implementation engineer — onboarding is self-serve, with optional white-glove support for teams >25 seats.

---

### 15. Do you have a public roadmap?

**Short:** We share roadmap with paying customers under NDA. The big things in 2026 are SOC 2 Type II, on-premise deployment, and a public API.

**Long:** We don't publish a marketing roadmap because we change priorities based on customer signal, and we don't want a "promised in Q2, slipped to Q4" pattern. Paying customers get access to a shared roadmap document, updated monthly, including known limitations and what's actively being worked on. The high-confidence 2026 items are SOC 2 Type II readiness, the on-premise SKU, and a public REST API.

---

## Common objections (with how to handle them)

### "We already have HubSpot — why would we need this?"

HubSpot is a CRM. [PRODUCT NAME] is what fills HubSpot in the first place. Without us, your reps have to remember to log every inbound lead, write a summary, and update status — most don't, and that's how leads get lost. We are the layer between Gmail and HubSpot.

### "We're too small for this."

Two follow-ups: (1) How many inbound leads do you get a month? If the number is over ~30, dropping 25% of them is a real cost. (2) Smaller teams have less margin to lose leads; the tool's leverage is bigger when there's no SDR to backstop the founder's inbox.

### "Won't AI hallucinate and make us look bad?"

Three pieces of armor here: (1) Every summary links to the source thread, so a rep can verify in seconds. (2) Ambiguous emails are flagged for human review — we don't ship false confidence. (3) The summary is a *summary*, not an outbound message. We're not auto-replying.

### "We tried [Otter / Gong / Lavender] and didn't get value."

Different category. Those are conversation tools — they listen to calls. [PRODUCT NAME] is an inbox tool — it watches email. The pain is different: leads buried in threads, not call quality. The two are complementary, not overlapping.

### "I need to see ROI before I can sign off."

Send the ROI one-pager (`12_roi_one_pager.md`) before the next call. Walk through their actual numbers: leads/month × drop rate × deal size × close rate = pipeline lost. The math typically self-justifies in the first week.

### "Why not just build this with ChatGPT?"

Three reasons: (1) Sending customer email content to ChatGPT is a security review failure for most B2B firms. (2) The product is not the prompt — it's the watcher pipeline, the tracker, the duplicate-merging logic, the deck generator, and the audit log. The prompt is 5% of it. (3) "Just build it" assumes engineering bandwidth that most teams don't have for an internal tool.
