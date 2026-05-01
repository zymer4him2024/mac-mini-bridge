# Comparison Sheet — [PRODUCT NAME] vs. The Alternatives

A buyer-honest side-by-side. The goal is not to make every column favor us — it's to be the one vendor that tells the truth, so the prospect trusts us by the time we get to the close.

> **Send this when:** A prospect says "we're also evaluating X." Pre-emptively differentiating before the comparison happens in their head.

---

## At a glance

| Capability | [PRODUCT NAME] | HubSpot Inbox | Salesforce Inbox / Einstein | Manual SDR triage | Otter / Gong + CRM |
|---|---|---|---|---|---|
| Auto-summarize inbound emails | ✅ | Partial *(in beta)* | Partial | ❌ | ❌ |
| Auto-update lead tracker | ✅ | ✅ *(in HubSpot only)* | ✅ *(in Salesforce only)* | Depends on rep | ❌ |
| Weekly auto-generated deck | ✅ | ❌ | ❌ | ❌ | ❌ |
| Local AI / no third-party LLM | ✅ | ❌ | ❌ | N/A | ❌ |
| On-premise deployment option | ✅ *(roadmap, designed-in)* | ❌ | ❌ *(Hyperforce ≠ on-prem)* | N/A | ❌ |
| Works with any inbox (Gmail, Outlook, IMAP) | ✅ | Partial | Partial | ✅ | ✅ |
| Setup time | 90 seconds | 1–2 days *(CRM setup)* | 1–4 weeks *(implementation partner)* | 0 days | 1 day |
| Starting price | [$X]/mo per inbox | $890+/mo *(includes CRM)* | $1,500+/mo *(includes CRM)* | Cost of an SDR | $400+/mo *(stack)* |
| You also need a CRM? | Optional *(complements yours)* | No *(CRM is the product)* | No *(CRM is the product)* | Yes | Yes |

> Legend: ✅ native · ❌ not available · *Partial = available but not the primary use case for that product.*

---

## The honest read on each alternative

### vs. HubSpot Inbox

**Where HubSpot wins.** If you don't have a CRM yet and you want one platform for marketing, sales, and service, HubSpot is the obvious choice. Their inbox features are improving. Their integration story (forms, workflows, sequences) is deep.

**Where we win.** HubSpot wants you to live inside HubSpot. We want to feed your existing tools. If your team already uses Gmail or Outlook as their day-to-day inbox (which is most teams), [PRODUCT NAME] sits between the inbox and your CRM and updates both — without forcing your reps to context-switch into a new app. We are also dramatically cheaper as a starting point because we don't bundle a CRM you may not need.

**The honest answer.** If you don't have a CRM and don't want one, HubSpot is a fine stack. If you have a CRM (any CRM) and the problem is leads-not-getting-into-it, we're better positioned.

---

### vs. Salesforce Inbox / Einstein

**Where Salesforce wins.** Enterprise scale, RBAC, governance, a partner ecosystem the size of a small country. If you are a 1,000-person organization with a Salesforce admin team, this is your default.

**Where we win.** Two places. First, time-to-value: Salesforce inbox features typically require a 4-week implementation engagement. We are running on your inbox in 90 seconds. Second, deployment optionality: Salesforce Einstein sends data through Salesforce's AI cloud (improving, but still a third-party LLM dependency for many configurations). We run inference locally — survives the security review that Salesforce's cloud-AI configuration sometimes does not.

**The honest answer.** If you're a Salesforce customer and you have an admin team, Einstein is a reasonable default for inbox AI. If your security team has already pushed back on cloud-AI features, we are the alternative that doesn't make you abandon Salesforce — we feed it.

---

### vs. Manual SDR triage

**Where manual wins.** Judgment. A great SDR can read between the lines, recognize a key account from a free email domain, and flag a "this looks like nothing but is actually a whale" thread. AI cannot fully replace that.

**Where we win.** Volume, consistency, and Friday afternoons. SDRs are great when they're paying attention; they're the cost center of a follow-up gap when they're not. [PRODUCT NAME] doesn't get tired, doesn't take PTO, and doesn't get pulled into outbound campaigns the week your inbound surges. The right answer is usually **both** — let SDRs spend their time on outbound and on the leads our system flagged as "Needs Human Review."

**The honest answer.** Don't fire your SDRs. Free them up.

---

### vs. Otter / Gong + CRM stack

**Where Otter / Gong win.** Conversation intelligence — they listen to your calls and tell you what was said. Different problem entirely.

**Where we win.** We're not in the same category. Their pain is "what happened on the call?" Our pain is "what's coming in via email?" The two stacks complement each other; many of our customers run both. The trap is treating them as substitutes — they aren't.

**The honest answer.** If your sales process is mostly phone-based, prioritize Gong. If it's mostly inbound email, start with us. If it's both, run both — the stacks don't overlap.

---

### vs. "we'll just build it ourselves with ChatGPT"

**Where DIY wins.** Total control. Customization to your exact pipeline. Zero recurring vendor cost (in theory).

**Where we win.** Three things, all of which look small upfront and large after 90 days:

1. **The pipeline isn't the prompt.** Watching the inbox, classifying emails, deduplicating leads, generating decks, writing audit logs — that's a real product, not a prompt. Internal builds usually ship the prompt and never the rest.
2. **Security posture is doing real work.** Sending customer email content to ChatGPT fails most security reviews. Building your own internal local-AI pipeline is a 6-month engineering project for someone who is already busy.
3. **Maintenance is invisible until it isn't.** The build is one project; the keep-it-working-forever is the cost.

**The honest answer.** Build it yourself if (a) you have a senior ML engineer with bandwidth, (b) inbound lead automation is a strategic moat for your business, and (c) you've estimated the 5-year TCO honestly. For most B2B teams, none of those is true.

---

## When NOT to pick us

We are not the right answer if:

- **Your sales motion is primarily outbound.** We process inbound. Outbound prospecting tools (Apollo, Outreach, Smartlead) solve a different problem. Buy those first.
- **You don't have a CRM and don't want one and have <5 leads/week.** A spreadsheet works. We're overkill at that volume.
- **You need HIPAA-grade compliance today.** SOC 2 Type II is on the roadmap; HIPAA BAAs are not 2026 work. Ask again next year.
- **You sell exclusively in countries we haven't deployed in.** Mostly a non-issue (we're inbox-based), but the SaaS topology is currently US/EU-hosted.

We'd rather lose a deal we can't serve than win one and disappoint.

---

## Talk track for the comparison conversation

**When the prospect says "we're also looking at HubSpot":**

> "Good. HubSpot is the right answer for some teams. Let me ask one question — do you already have a CRM you're committed to? *(If yes:)* Then HubSpot is asking you to migrate. We sit in front of whatever CRM you have. *(If no:)* HubSpot is a more complete platform and a more expensive starting point. The right comparison isn't us vs. HubSpot Inbox — it's us-plus-your-CRM-of-choice vs. HubSpot's full stack."

**When they say "we'll just have our SDR do it":**

> "Probably the right call for the first 50 leads. The question is the 200th lead, on the Friday before a holiday weekend. We don't replace SDRs — we make sure the work gets done when the SDR is doing something else."

**When they say "we're going to build it":**

> "Most teams who say that ship a prompt and never the rest. The AI summary is 5% of the product; the watcher pipeline, the dedupe logic, the deck generator, and the audit trail are the other 95%. If you have a senior ML engineer with a free quarter, build it. If not, the math on us is hard to beat."
