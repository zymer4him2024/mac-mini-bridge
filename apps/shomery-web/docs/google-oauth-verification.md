# Google OAuth Verification — Submission Package

**Status:** Draft. Ready to file once the two pre-filing blockers below clear.
**Owner:** Project owner (Shawn). Verification can only be filed from the Google Cloud Console by the project's verified owner.
**Last updated:** 2026-05-01.

---

## 1. Decision: which scope to request

**Request `https://www.googleapis.com/auth/drive.file` only.** Do **not** request `https://www.googleapis.com/auth/drive` (full).

| Scope | Tier | Verification needed | CASA assessment |
|---|---|---|---|
| `drive.file` | **Non-sensitive** | Light: brand verification + privacy policy. No formal sensitive/restricted review. | **None.** |
| `drive` (full) | Restricted | Full submission, demo video, scope justification. | **Required**, annual, ~4–8 weeks, ~$3k–$15k. |

**Why `drive.file` is sufficient.** With `drive.file`, the app gets per-file access to files it creates *or* files the user explicitly hands to it via the Google Picker. Shomery's flow fits cleanly:

1. User picks a folder via Google Picker → app receives the folder ID with permission.
2. Watcher creates `.md` files inside that folder → app retains access to its own creations forever.
3. Web reads those `.md` files back to render the markdown viewer → still its own creations.

Listing files under that folder via `files.list` returns only files the app created — exactly the behaviour we want. We never need to see arbitrary user files outside Shomery's own writes. (Source: https://developers.google.com/workspace/drive/api/guides/api-specific-auth)

**This changes CLAUDE.md.** *Critical things NOT to do* #3 currently says verification is "4–8 weeks" with "possible CASA." Update that line once we file: with `drive.file`, the realistic window is **3–5 business days for sensitive-scope verification, no CASA**. The CLAUDE.md *External lead-time tasks* note should also be updated to reflect the lower tier.

---

## 2. Pre-filing blockers (must clear before submitting)

### 2.1 Domain decision

The OAuth consent screen, app homepage, and privacy policy URL must all live on the **same verified domain**. We have two choices:

- **(A) Use `shomeryai.web.app`** (the existing Firebase Hosting domain). Pros: zero lead time, already verified by Firebase, can file today. Cons: not a custom-branded domain.
- **(B) Wait for `shomery.com`** (per CLAUDE.md *External lead-time tasks*). Pros: branded URL on the consent screen. Cons: domain registration + DNS + Search Console verification adds 1–2 weeks before we can even file.

**Recommendation: file with `shomeryai.web.app` now**, switch to `shomery.com` post-launch via re-verification. The consent screen URL is a string we can change later; what matters is that the verification package itself lands quickly.

### 2.2 Privacy policy

We don't have a public privacy policy yet. Verification requires one at a stable URL on the verified domain, linked from the consent screen and the app homepage. Draft language for the Drive-relevant section is in §5 below; the policy itself needs to also cover identity, Firestore data, Firebase Storage, retention, deletion, and contact — out of scope for this doc.

**Action:** publish `https://shomeryai.web.app/privacy` (or equivalent) before filing. Static page is fine.

---

## 3. Submission checklist

These are the fields Google requires (source: https://support.google.com/cloud/answer/13464321):

- [ ] **App homepage URL** on the verified domain. → `https://shomeryai.web.app/`
- [ ] **Privacy policy URL** on the same domain, linked from homepage and consent screen. → `https://shomeryai.web.app/privacy` *(blocked on §2.2)*
- [ ] **Domain ownership** verified in Google Search Console for `shomeryai.web.app`. *(Firebase auto-verifies; confirm in GSC.)*
- [ ] **Project contact email** set on the OAuth consent screen. → use a monitored address, not a personal account.
- [ ] **App name** in the consent screen. → `Shomery`
- [ ] **App logo** (120×120 px PNG, transparent background, on-brand emerald monogram). → derive from `src/app/icon.tsx`.
- [ ] **Authorized JavaScript origins** finalised. → `https://shomeryai.web.app` (+ `http://localhost:3000` for dev).
- [ ] **Authorized redirect URIs** finalised. → as currently configured for Firebase Auth.
- [ ] **Scope** added: `https://www.googleapis.com/auth/drive.file` (only).
- [ ] **Scope justification** text (see §4 below) pasted into the consent-screen scope-justification field.
- [ ] **Demo video** *(only required for sensitive/restricted scopes — `drive.file` is non-sensitive, so this may not be requested. Have one ready in case Google asks. Script in §6.)*
- [ ] Submit for verification.

---

## 4. Scope justification text (paste-ready)

When the consent screen asks "Why does your app need this scope?" for `drive.file`, paste:

> Shomery is a private notebook over a user's email inbox. After the user grants access, the app saves a markdown summary of each watched email as a file in a Google Drive folder of the user's choice (selected via the Google Picker). The user reads, exports, or deletes these files at any time from inside Shomery.
>
> The `drive.file` scope is the narrowest scope that enables this flow: it grants per-file access only to files Shomery creates, plus files the user explicitly opens with Shomery via the Google Picker. Shomery never reads, lists, or modifies any other file in the user's Drive. We do not request `drive`, `drive.readonly`, or `drive.metadata` because Shomery has no need to enumerate or access files it did not create.

---

## 5. Privacy policy — Drive-relevant additions (paste-ready)

Add these sections to the published privacy policy. (The full policy needs more — identity data, retention, deletion, contact — but these are the **Drive-specific** disclosures Google's reviewers will look for.)

### Google user data — what we access

> When you connect Google Drive, Shomery requests the `drive.file` scope. This grants Shomery permission to:
> - Create new files in the Drive folder you select.
> - Open files you have explicitly handed to Shomery via the Google Drive picker.
>
> Shomery cannot list, read, or modify any other file in your Drive. We do not have access to your full Drive contents and we never request that access.

### How we use Google user data

> Shomery uses your Drive solely to save the markdown summaries it generates from your watched emails, and to render those summaries back to you inside the app. We do not transfer your Drive data to any third party. We do not use it for advertising, model training, or analytics.

### Google API Services User Data Policy compliance

> Shomery's use of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

---

## 6. Demo video script — `drive.file` flow

*Have this ready but unrecorded until Google asks. For non-sensitive scopes the video is sometimes waived.* If recorded: 60–90 seconds, screen recording, no narration required (captions are sufficient).

1. **(0:00–0:10)** Open `https://shomeryai.web.app`. Show the homepage and the visible link to the privacy policy.
2. **(0:10–0:25)** Click *Sign in with Google*. Show the OAuth consent screen with **Shomery** as the app name and `drive.file` as the requested scope. Click *Allow*.
3. **(0:25–0:50)** Land in onboarding step 3 (*Where summaries live*). Click *Choose folder*. The Google Picker opens. Select a folder. The picker closes; the chosen folder name renders in the callout (replacing the placeholder).
4. **(0:50–1:10)** Open Drive in another tab to show the (initially empty) chosen folder. Trigger a watched email summary (or use a demo seed). Refresh — the new `.md` file appears in the user's chosen folder.
5. **(1:10–1:25)** Back in Shomery, open the same item from the Feed. The markdown viewer renders the file content read from Drive via `drive.file`.
6. **(1:25–1:30)** Optional: hit Drive's *trash* on the file — confirm Shomery shows the empty state, demonstrating it does not retain data outside the user's Drive.

Captions to include on-screen as text overlays: "Shomery requests `drive.file` only", "Shomery only sees files it creates or files you hand it via the picker", "Shomery never lists your Drive."

---

## 7. After verification clears

1. **Update CLAUDE.md** *Critical decisions* #1, *Critical things NOT to do* #3, and *External lead-time tasks* — flip from "in review / blocked" to "live."
2. **Build the picker integration** in a single PR (the previously-deferred Drive code). Touchpoints:
   - `getMarkdown(item)` helper — add the `drive://` branch.
   - Onboarding step 3 — replace placeholder callout with a *Choose folder* button → Google Picker.
   - Settings → Where to save — same picker, plus "Change folder" / "Disconnect Drive" actions.
   - `firestore_users.py` and Firestore rules — add `driveFolderId` and `driveFolderName` fields under `users/{uid}/config/main`.
   - Watcher (`watcher.py`) — branch on `driveFolderId` presence: write to Drive when set, fall back to Firebase Storage when not (covers users who skip the picker).
3. **Custom domain swap** (if not done already): re-verify the consent screen on `shomery.com` once that domain is registered.

---

## 8. Filing log (fill in once filed)

| Date | Action | Notes |
|---|---|---|
| YYYY-MM-DD | Privacy policy published at … | |
| YYYY-MM-DD | Verification submitted | Project: …, contact: … |
| YYYY-MM-DD | Google response | |
| YYYY-MM-DD | Verification cleared | |
