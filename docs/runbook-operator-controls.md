# Operator controls runbook

Phase B7 in the enterprise hardening plan: tighten the operator-side
attack surface so a compromised host or laptop cannot mint long-lived
credentials against the production project.

## Goals

1. Remove `firebase-service-account.json` from the worker host filesystem.
2. Rotate any service-account key that ever sat on disk.
3. Capture an access-review cadence (Phase D4) so the right people remain
   on the right roles.

## Mac Mini tenant (current production)

Today the workers authenticate via `firebase-service-account.json` at the
repo root (`chmod 600`, owner-only). That key file:

- is a static credential — anyone who can read it gets unbounded API
  access until rotation;
- replicates onto every Time Machine backup;
- is what an attacker grabs first if they get shell on the Mac Mini.

### Target state

Authenticate via Workload Identity Federation (WIF) bound to the Mac
Mini's machine identity. WIF on macOS is constrained, so the practical
hardening is:

1. **Move the key into Secret Manager and pull at startup.**
2. **Reduce role scope** to the minimum the workers need.
3. **Tag the key with a 90-day rotation reminder.**

### Steps

1. Create a Google Secret Manager secret with the JSON:

   ```sh
   gcloud secrets create email2ppt-worker-sa \
     --replication-policy automatic \
     --project <project>

   gcloud secrets versions add email2ppt-worker-sa \
     --data-file firebase-service-account.json \
     --project <project>
   ```

2. Bind a thin **bootstrap** identity (laptop user gcloud creds, or a
   short-lived OAuth) that has only `roles/secretmanager.secretAccessor`
   on this one secret. This is the only identity the host needs to keep
   on disk; it cannot read or write Firestore directly.

3. Replace the `firebase-service-account.json` on the Mac Mini with a
   small launch wrapper that fetches the secret on each launchd cycle:

   ```sh
   #!/bin/sh
   set -eu
   gcloud secrets versions access latest \
     --secret email2ppt-worker-sa \
     --project <project> \
     > "$(dirname "$0")/firebase-service-account.json"
   chmod 600 "$(dirname "$0")/firebase-service-account.json"
   exec "$(dirname "$0")/venv/bin/python" "$@"
   ```

   Point the `ProgramArguments` in every plist
   (`com.shawn.email-watcher.plist`, `email-digest.plist`, etc.) at this
   wrapper. The fetched file lives only for the duration of the run —
   add a trap to delete it on exit if the worker is short-lived.

4. **Reduce role scope.** Replace any broad `roles/firebase.admin` or
   `roles/editor` on the worker SA with the narrowest set:

   - `roles/datastore.user` — Firestore read/write.
   - `roles/cloudkms.cryptoKeyEncrypterDecrypter` — only on the
     `app-secrets` key; do NOT grant project-wide.
   - No Cloud Storage or IAM admin.

5. **Tag rotation.** In the IAM Console, add `email2ppt-rotation=90d`
   label to the SA so the next access review surfaces it.

## Cloud Run tenants (Phase C)

For per-tenant Cloud Run services, do not provision SA keys at all.
Bind the runtime service account directly via:

```sh
gcloud run services update <service-name> \
  --service-account email2ppt-tenant-<uid>@<project>.iam.gserviceaccount.com \
  --region us-central1
```

Cloud Run mints short-lived OAuth tokens against the bound SA on each
request — no static credential is on disk.

## Rotation procedure

Manual rotation (run quarterly, or immediately on suspected compromise):

1. Disable the current key:
   ```sh
   gcloud iam service-accounts keys disable <key-id> \
     --iam-account email2ppt-worker@<project>.iam.gserviceaccount.com
   ```

2. Mint a new key:
   ```sh
   gcloud iam service-accounts keys create new-sa.json \
     --iam-account email2ppt-worker@<project>.iam.gserviceaccount.com
   ```

3. Push to Secret Manager:
   ```sh
   gcloud secrets versions add email2ppt-worker-sa \
     --data-file new-sa.json
   shred -u new-sa.json   # never persist the JSON to local disk
   ```

4. Restart workers. The next launchd cycle picks up the new version.

5. After 7 days of clean operation, delete the disabled key:
   ```sh
   gcloud iam service-accounts keys delete <key-id> \
     --iam-account email2ppt-worker@<project>.iam.gserviceaccount.com
   ```

## Quarterly access review (Phase D4 hook)

Every 90 days, the operator runs:

```sh
gcloud projects get-iam-policy <project> --format=json > iam-snapshot.json
gcloud kms keys get-iam-policy app-secrets \
  --location us-central1 --keyring email2ppt --format=json \
  > kms-iam-snapshot.json
```

Diff against the previous snapshot. Any added member that does not have
a corresponding ticket should be revoked the same day.

## Logging

Cloud Audit Logs for Firestore Admin reads, KMS Encrypt/Decrypt, and
Secret Manager `accessSecretVersion` are enabled by default at the
Admin Activity tier. To capture Data Access reads (which are off by
default), add to `gcloud organizations get-iam-policy` enablement, or
set on the project:

```sh
gcloud projects set-iam-policy ... # Data Access logging policy
```

This is what an auditor expects to see during SOC 2 fieldwork.
