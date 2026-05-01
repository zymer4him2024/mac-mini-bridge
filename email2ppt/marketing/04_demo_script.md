# Demo Script & Talk Track — [PRODUCT NAME]

A 15-minute structured demo for a first sales call. The shape: 3 minutes discovery, 2 minutes problem framing, 7 minutes live demo, 3 minutes close. **Ratio matters** — most failed demos talk too much before listening.

> **The mantra:** Tell them what they're going to see, show them, then ask them what they think. Three times.

---

## Pre-call preparation (5 min before)

- Confirm their job title, team size, and inbound lead volume (LinkedIn, their website careers page, prior emails).
- Have a clean test inbox loaded with 8–10 realistic-looking sample emails. Mix of clear leads, ambiguous emails, and clearly-not-a-lead. (Build this once, reuse.)
- Have the SMB pitch deck open in a second tab in case the demo breaks. It's your safety net, not your primary tool.
- Pre-send no slides. The product is the show.

---

## 0:00 – 3:00 — Discovery (you ask, they talk)

**Opening line.** "Thanks for the time. Before I show you anything, I want to make sure I understand your setup so I can show you the parts that actually matter to you. Three quick questions, then we'll get to the screen share."

**Question 1.** "How does an inbound sales email get from your sales@ inbox into your pipeline today? Walk me through what happens, step by step."

*Listen for:* Manual SDR triage. Reps forgetting to log leads. CRM staleness. Founder triaging their own inbox. Spreadsheets. Slack channels.

**Question 2.** "Roughly how many inbound leads land each week, and what percentage of them do you think actually get followed up on within 48 hours?"

*Listen for:* They almost always underestimate the drop rate. The number you hear is the optimistic version.

**Question 3.** "If you had a perfect Monday-morning view of your inbound pipeline, what would it show you that you can't see today?"

*Listen for:* This is the single most useful question. Their answer is your closing argument.

> **If you only have 5 minutes**, skip the rest of the script and ask Question 3 first. The whole demo collapses into "let me show you that exact view."

---

## 3:00 – 5:00 — Problem framing (you talk, briefly)

> "Based on what you just told me, you're losing roughly [X] leads a week to follow-up gaps. Even at a conservative deal size and close rate, that's a real number — let's say [$X] in pipeline a month.
>
> The reason isn't your team. It's that the work of summarizing, tracking, and reporting on inbound leads is invisible labor — it doesn't have an owner, it always loses to the urgent thing in front of someone, and so it doesn't happen.
>
> [PRODUCT NAME] takes that work off your team's plate entirely. Three things — let me show you each one in 90 seconds."

> **Don't pitch features here.** The job of these two minutes is to make them nod, not to oversell.

---

## 5:00 – 12:00 — The Live Demo (in three movements)

### Movement 1 — "Read once, never again" (90 seconds)

> "I have a test inbox here that just received eight new emails. Watch what happens to one of them."

*Click into a single ambiguous-but-real-looking sales email. Wait 5–8 seconds for the summary to appear in the lead card.*

> "200-word summary. Sender intent. Key requirements. Budget signal if it's there. Priority level. Your rep doesn't have to re-read this thread. Your manager doesn't have to ask 'what was that one about?' on Friday.
>
> What does this look like in your world today?"

*Pause. Let them answer. The pause is the demo.*

### Movement 2 — "Your CRM, finally up to date" (90 seconds)

> "Now look at the tracker."

*Click to the lead tracker view. Show 30+ leads with status, owner, last-touched date.*

> "This is the source of truth. Every relevant inbound from the past 90 days. Status. Owner. Last-touched. Nobody had to type any of this — it built itself.
>
> If you're a HubSpot or Salesforce customer, this also pushes downstream into the CRM. We're not a CRM replacement; we're the layer that fills the CRM in the first place.
>
> Does this answer the 'what's in our pipeline this week?' question better or worse than what you have today?"

*Pause.*

### Movement 3 — "Monday-morning decks, written for you" (90 seconds)

> "Last one. This is the email you'd get every Monday at 8am."

*Click to a sample weekly report email. Open the attached deck.*

> "Twelve slides. New opportunities, conversion metrics, pipeline movement, leads at risk, suggested actions. Your AE can forward this directly to a customer if it's relevant. Your sales lead can walk into Monday's meeting without prepping anything.
>
> What would have to be true for your team to use this every Monday?"

*This is a buying signal question. Their answer is the spec for the rest of the conversation.*

---

## 12:00 – 15:00 — Close (or schedule the next step)

### If you're getting clear buying signals:

> "Based on what we just walked through — what's the next step on your side?"

*Stay quiet. Let them propose the next step. Whatever they say, you say "great, let's do that."*

### If they're warm but not committing:

> "I think the way to make this real is a 14-day trial on your actual sales@ inbox. By day 4 you'll have 20+ summaries to evaluate. By day 7 you'll see your first weekly report. No credit card. We can have it running by [DAY THIS WEEK].
>
> Is there anyone else who'd need to be in the loop before we kick that off?"

### If they're skeptical:

> "Totally fair. Two things might help: I can send the security review packet so your IT team can pre-clear it, and I can send the ROI one-pager so you can run the numbers on your own time. Want both?"

*This buys you the next email and keeps them inside the funnel.*

### If they're a hard "no":

> "Understood. Can I ask — is the 'no' that you don't have the problem, or that you have the problem but [PRODUCT NAME] isn't the right shape of solution?"

*The answer to this question is the most valuable thing you'll learn all week. Write it down. Their objection is your roadmap.*

---

## Common live-demo questions (and your prepared answers)

**"Where does the AI run?"**
> "Locally, on the inbox owner's hardware in the on-prem topology, or on dedicated hardware we manage in the SaaS topology. Email content does not leave that boundary. There's no third-party LLM call. We can demo this in a network packet capture during a security review."

**"What if the AI gets a summary wrong?"**
> "Two things. The lead card always links to the source thread, so verification is two clicks. And we deliberately flag ambiguous emails for human review instead of generating false confidence — that's a design choice, not an accident."

**"How does this compare to HubSpot's AI features?"**
> "HubSpot's AI summarizes inside HubSpot. The problem we solve is one step earlier: getting the email into HubSpot in the first place, accurately and consistently. We're complementary; most of our customers also run HubSpot."

**"Can we self-host?"**
> "Yes — same product, configured to run on your hardware. The codebase has two clean abstraction seams that select between cloud and local backends via one config flag. Pricing is different. I can send the on-prem deployment guide if it's relevant."

**"What's pricing?"**
> "Starts at [$X]/mo for teams up to 5 inboxes. Team tier is [$X]/mo for up to 25. Enterprise is custom. Annual gets 20% off. Should I send the full pricing page after the call?"

---

## Demo anti-patterns (don't do these)

- **Don't read your slides.** If you're tempted to use slides, the product is broken or the rep is.
- **Don't go feature-by-feature.** Every demo movement should answer a question they asked.
- **Don't apologize for what's missing.** "We don't have integration X yet" → "Integration X is on the roadmap; today's customers route around it via Zapier."
- **Don't extend past 15 minutes uninvited.** If they want longer, they will say so. Ending early is a feature.
- **Don't promise pricing flexibility on the call.** "Let me come back with a proposal" is a fine answer. Negotiating live signals desperation.

---

## Post-call (within 30 minutes)

Send a follow-up email that contains, in order:

1. Thank them for the time.
2. Recap the three things they said they care about (proves you listened).
3. The two assets that match the conversation: the relevant pitch deck PDF + the ROI one-pager.
4. The proposed next step — with a calendar link, not a "let me know."

Keep it under 120 words.
