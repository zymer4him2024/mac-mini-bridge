# Cold Email Sequences — [PRODUCT NAME]

Three 5-step sequences, one per buyer persona. Each step ≤120 words, single CTA, no attachments, plain text only. Send Tuesday/Thursday, 9–11am local time of the prospect.

**General rules**

- Personalize the first line of step 1 (a real fact about their company). Everything else can be templated.
- Reply to your own previous email instead of starting a new thread (preserves context, raises open rate).
- Stop sequencing on any reply, including "not interested." Move them to manual.
- After step 5, mark dormant. Do not re-sequence for 90 days.

---

## SEQUENCE 1 — SMB Sales Leaders *(primary persona)*

**Target.** VP of Sales, Head of Sales, Sales Operations Lead at 10–200-person B2B firms.
**Hook.** Pipeline visibility + leads not dropped.

### Step 1 — Day 0

**Subject A:** quick question on inbound leads at [Company]
**Subject B:** how does [Company] track inbound right now?

Hi [First Name],

Saw you posted about [scaling the SDR team / hiring two AEs / their last fundraise]. Congrats.

Quick question — when a new inbound email lands in sales@[company].com, how does it get tracked today? Most teams I talk to either rely on Salesforce/HubSpot reps remembering to log it, or have an SDR triaging by hand on Monday.

[PRODUCT NAME] is a small tool that watches that inbox and auto-summarizes every lead, updates your tracker, and sends you a Monday deck. Teams typically recover 10–15 hours a week and stop losing leads to follow-up gaps.

Worth a 15-minute look?

— [Your Name]

---

### Step 2 — Day 3 (reply to Step 1)

**Subject:** *(empty — reply preserves thread)*

Hi [First Name],

In case the question got lost: most sales teams I see lose 1 in 4 inbound leads to follow-up gaps, almost always because nobody summarized the thread on day 1.

[PRODUCT NAME] writes a 200-word summary of every relevant inbound the moment it arrives, and adds it to a tracker your whole team sees.

If "we don't have a tracking problem" is the answer, totally fair — happy to drop off.

— [Your Name]

---

### Step 3 — Day 7

**Subject:** [PRODUCT NAME] — 90-second video

Hi [First Name],

Rather than another email, here's a 90-second walkthrough of what [PRODUCT NAME] does on a real inbox: [LOOM LINK]

The most common reaction from sales leaders: "wait, is that just running automatically?" Yes.

If it's relevant, my calendar is here: [CALENDLY LINK].

— [Your Name]

---

### Step 4 — Day 12

**Subject:** one number for [Company]

Hi [First Name],

A quick sanity check. If your team gets ~[X] inbound leads a month and 25% get dropped due to follow-up gaps, that's [X * 0.25] missed opportunities a month.

Even at a conservative [$5K] per closed deal and a 10% close rate, that's roughly [$X * 0.25 * 0.1 * 5000] in pipeline lost per month.

[PRODUCT NAME] starts at [$X]/mo. The math usually shows ROI inside the first week.

15 minutes? [CALENDLY LINK]

— [Your Name]

---

### Step 5 — Day 21 (the breakup)

**Subject:** closing the loop

Hi [First Name],

I won't keep emailing — assuming the timing isn't right.

If it ever becomes relevant, the homepage has a 90-second demo: [URL]. I'll check back in Q[X].

Best of luck with [recent thing they're working on].

— [Your Name]

---

## SEQUENCE 2 — Enterprise Security / IT *(privacy-led)*

**Target.** CISO, VP Security, Head of Compliance at regulated B2B firms (financial services, healthcare, legal, defense suppliers, EU-headquartered).
**Hook.** Local AI, no data leaves the perimeter, GDPR-friendly.

### Step 1 — Day 0

**Subject A:** AI inbox tools and your data exhaust policy
**Subject B:** [Company]'s stance on third-party LLM access to customer email

Hi [First Name],

I imagine most "AI for sales" tools that have crossed your desk get rejected for the same reason: customer email content gets shipped to OpenAI / Anthropic / a third-party LLM, which fails most data-residency and DPA reviews.

[PRODUCT NAME] runs the AI locally — open-source model on customer hardware, no third-party LLM call, ever. Same product is available as SaaS or fully on-premise. The deployment topology is the customer's decision, not ours.

If you're getting pressure from sales leadership to "let us use AI," this is the version that survives security review.

Worth a short call to walk through the architecture?

— [Your Name]

---

### Step 2 — Day 4

**Subject:** *(reply to Step 1)*

Hi [First Name],

Two specific things you'll probably want to verify before any conversation:

1. **No third-party LLM call.** Inference is via Ollama running on customer hardware. We can demonstrate this in a network packet capture during the security review.
2. **Two seams already in the codebase.** State store and blob store are abstracted, so on-prem deployment is a configuration choice, not a separate fork.

Architecture overview here: [SECURITY LANDING PAGE URL]

— [Your Name]

---

### Step 3 — Day 9

**Subject:** Article 44 / SOC 2 packet for [PRODUCT NAME]

Hi [First Name],

We have a short security packet that covers:

- Data classification (control-plane vs. data-plane)
- DPA template
- Audit log format and retention
- SOC 2 Type II roadmap (in progress, honest about timeline)
- GDPR Article 44 attestation

Happy to send it under NDA. Reply with your standard NDA or use [DOCSEND LINK].

— [Your Name]

---

### Step 4 — Day 15

**Subject:** the question your sales team is going to ask

Hi [First Name],

Sales teams want AI-assisted lead summarization. Security teams want to keep email content inside the perimeter. Most tools force a tradeoff.

[PRODUCT NAME] doesn't, because the architecture was designed around your constraint, not against it.

15-minute architecture walkthrough? [CALENDLY LINK]

— [Your Name]

---

### Step 5 — Day 25 (the breakup)

**Subject:** closing the loop on AI inbox tools

Hi [First Name],

Last note from me. If your sales org ever asks for an AI inbox tool that survives a security review, I'd love to be on the shortlist.

In the meantime, the architecture page is at [URL] for reference.

Best,
[Your Name]

---

## SEQUENCE 3 — Founder-CEOs of small B2B firms *(do-it-all assistant angle)*

**Target.** Founder/CEO of 2–25-person professional services or B2B firms where the CEO is still answering inbound directly.
**Hook.** Get your inbox out of your head.

### Step 1 — Day 0

**Subject A:** still answering your own inbox?
**Subject B:** [First Name] — quick one for a fellow founder

Hi [First Name],

Founder-to-founder, indulge me for 30 seconds.

If you're like most CEOs of [size] firms, you're still personally triaging inbound at sales@[company].com or your own inbox. Each new lead is a context switch you don't have time for, and a quarter of them slip through the cracks.

[PRODUCT NAME] is a small tool I built (originally for myself) that watches the inbox, summarizes every relevant lead, and sends you a Monday morning deck of what came in last week. No CRM logins. No Zapier setup.

Worth 10 minutes?

— [Your Name]

---

### Step 2 — Day 4

**Subject:** *(reply to Step 1)*

Hi [First Name],

The honest pitch is: the time you spend re-reading email threads at 9pm is the highest-leverage time you can buy back.

[PRODUCT NAME] is [$X]/mo. If it saves you four hours a week, the math works. Most founders I've shown it to recover the cost in the first week.

— [Your Name]

---

### Step 3 — Day 8

**Subject:** what Monday morning looks like with [PRODUCT NAME]

Hi [First Name],

Picture Monday at 8am. Your inbox has 73 unread items. Instead of clicking through them, you open one email from [PRODUCT NAME] with:

- 12 new inbound leads, ranked by priority
- A 200-word summary of each
- A slide deck you can forward to your AE without writing a word

That's the product. 90 seconds to see it: [LOOM LINK].

— [Your Name]

---

### Step 4 — Day 14

**Subject:** for [Company]'s next 12 months

Hi [First Name],

You're going to hire [a salesperson / an EA / a first SDR] in the next 12 months. The biggest shift founders describe is realizing how much "tracking and summarizing" they were doing in their head — that nobody else can pick up cleanly.

[PRODUCT NAME] makes that handoff 10x easier because the lead history is already written down.

10 minutes? [CALENDLY LINK]

— [Your Name]

---

### Step 5 — Day 24 (the breakup)

**Subject:** last note

Hi [First Name],

I'll stop here. If your inbox starts winning the day-to-day battle, the door is open: [URL].

Building something on the side too — happy to swap notes anytime.

— [Your Name]

---

## Subject line A/B test ideas

When you have enough volume (300+ sends per variant), test these against the defaults:

- **Curiosity:** "one number for [Company]"
- **Direct ask:** "15 min next Tuesday?"
- **Numerical:** "73 leads, 18 dropped — sound familiar?"
- **First-name only:** "[First Name]"
- **Question:** "do you log every inbound lead?"

**Stop testing what you can't measure.** Without an outbound platform tracking opens/clicks, sequence quality > clever subject lines.
