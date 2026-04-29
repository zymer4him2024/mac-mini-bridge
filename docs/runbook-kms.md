# KMS provisioning runbook

This is the one-time provisioning required before B1 (envelope encryption
of refresh tokens and bot tokens) is active. Until you finish this, the
new `wrap_token`/`unwrap_token` paths are no-ops and tokens stay in
plaintext. After you finish, every new token write is KMS-wrapped, and
the migration step upgrades existing tokens.

## Prerequisites

- `gcloud` CLI authenticated as a project owner.
- Project ID: substitute `<project>` below.
- Region: `us-central1` matches the Cloud Functions region today;
  multi-region (`us`) is also fine.

## 1. Enable the KMS API

```sh
gcloud services enable cloudkms.googleapis.com --project <project>
```

## 2. Create the keyring + key

```sh
gcloud kms keyrings create email2ppt \
  --location us-central1 \
  --project <project>

gcloud kms keys create app-secrets \
  --location us-central1 \
  --keyring email2ppt \
  --purpose encryption \
  --rotation-period 90d \
  --next-rotation-time "$(date -u -v+90d +%Y-%m-%dT%H:%M:%SZ)" \
  --project <project>
```

Resulting key resource name (the value of `KMS_KEY_NAME`):

```
projects/<project>/locations/us-central1/keyRings/email2ppt/cryptoKeys/app-secrets
```

## 3. Grant Cloud Functions access

The default Cloud Functions runtime SA is
`<project-number>-compute@developer.gserviceaccount.com` for v2 functions.
Confirm via the Console, then:

```sh
gcloud kms keys add-iam-policy-binding app-secrets \
  --location us-central1 \
  --keyring email2ppt \
  --member serviceAccount:<project-number>-compute@developer.gserviceaccount.com \
  --role roles/cloudkms.cryptoKeyEncrypterDecrypter \
  --project <project>
```

Set the param so the functions runtime can see the key name:

```sh
firebase functions:config:set kms.key_name="projects/<project>/locations/us-central1/keyRings/email2ppt/cryptoKeys/app-secrets" --project <project>
# or via .env / defineString — KMS_KEY_NAME is the variable name
```

Re-deploy:

```sh
firebase deploy --only functions
```

## 4. Grant the worker service account access

The Mac Mini and Cloud Run workers authenticate as the service account
whose key sits at `firebase-service-account.json` (Mac Mini) or whose
workload identity is bound (Cloud Run).

```sh
gcloud kms keys add-iam-policy-binding app-secrets \
  --location us-central1 \
  --keyring email2ppt \
  --member serviceAccount:<worker-sa-email> \
  --role roles/cloudkms.cryptoKeyEncrypterDecrypter \
  --project <project>
```

On the Mac Mini, append to `.env`:

```
KMS_KEY_NAME=projects/<project>/locations/us-central1/keyRings/email2ppt/cryptoKeys/app-secrets
```

Restart the launchd jobs so the new env is picked up:

```sh
launchctl unload ~/Library/LaunchAgents/com.shawn.email-watcher.plist
launchctl load   ~/Library/LaunchAgents/com.shawn.email-watcher.plist
# repeat for digest, config-sync, healthcheck
```

## 5. Migrate existing tokens

Once both runtimes can call KMS, sweep every plaintext refresh-token /
bot-token into ciphertext:

```sh
cd /Users/shawnlee/telegram-bridge
venv/bin/python migrate_kms_wrap.py
```

The script is idempotent (skips values already prefixed `kms:v1:`).

## 6. Verify

```sh
# Should print "True"
venv/bin/python -c "from kms_envelope import kms_configured; print(kms_configured())"

# Pick a uid and confirm the stored value starts with kms:v1:
gcloud firestore export ... # or read via admin script
```

## Rotation policy

The key rotates every 90 days. KMS auto-routes Decrypt to the right
version, so no app-side action is needed across rotations. Old key
versions remain enabled for decrypt for 30 days then move to
`destroy_scheduled` per GCP defaults — adjust via
`gcloud kms keys versions destroy` if you need a different window.

## Failure modes

- **`kms_not_configured`** raised on read: ciphertext exists but the
  worker / function has no `KMS_KEY_NAME`. Check the deployment env.
- **`PERMISSION_DENIED`** from KMS: the caller's service account is
  missing `roles/cloudkms.cryptoKeyEncrypterDecrypter` on the key.
- **Migration prints `bot_skipped` >> `bot_wrapped`**: this is normal on
  re-runs; means everything is already wrapped.
