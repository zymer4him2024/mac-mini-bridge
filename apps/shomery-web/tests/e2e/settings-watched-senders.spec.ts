/**
 * End-to-end Settings → Watched senders flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because the test
 * needs both the Firebase Auth emulator (for anonymous sign-in) and the
 * Firestore emulator (to verify the post-save state).
 *
 * To run locally:
 *   1. Start the Firebase Emulator Suite: `pnpm shomery:emulators`
 *   2. Start the dev server with emulator wiring on:
 *      `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm shomery:dev`
 *   3. Run: `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm --filter shomery-web test:e2e tests/e2e/settings-watched-senders.spec.ts`
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";

interface FirestoreDoc {
  fields?: {
    priorityWatchSenders?: {
      arrayValue?: { values?: { stringValue?: string }[] };
    };
  };
}

async function readWatchList(
  request: APIRequestContext,
  uid: string,
): Promise<string[]> {
  const url = `${FIRESTORE_HOST}/v1/projects/${PROJECT_ID}/databases/(default)/documents/users/${uid}/config/main`;
  const res = await request.get(url, {
    headers: { Authorization: "Bearer owner" },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to read config for ${uid}: ${res.status()} ${await res.text()}`,
    );
  }
  const body: FirestoreDoc = await res.json();
  return (body.fields?.priorityWatchSenders?.arrayValue?.values ?? [])
    .map((v) => v.stringValue ?? "")
    .filter(Boolean);
}

async function markOnboarded(
  request: APIRequestContext,
  uid: string,
): Promise<void> {
  const url = `${FIRESTORE_HOST}/v1/projects/${PROJECT_ID}/databases/(default)/documents/users/${uid}`;
  const res = await request.patch(url, {
    headers: { Authorization: "Bearer owner" },
    data: {
      fields: {
        onboardingCompletedAt: { timestampValue: new Date().toISOString() },
      },
    },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to mark onboarded for ${uid}: ${res.status()} ${await res.text()}`,
    );
  }
}

test.describe("settings → watched senders flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );

  test("a signed-in user can add a sender, save, and the value persists", async ({
    page,
    request,
  }) => {
    await page.goto("/en/sign-in");

    await page.waitForFunction(() => !!window.__shomeryE2E);
    const uid = await page.evaluate(() =>
      window.__shomeryE2E!.signInAnonymously(),
    );

    await markOnboarded(request, uid);

    await expect(page).toHaveURL(/\/en\/feed$/);
    await page.goto("/en/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    const watchedSenders = page.getByRole("region", {
      name: "Watched senders",
    });
    const input = page.getByPlaceholder("alice@example.com or @acme.com");
    await input.fill("bob@example.com");
    await watchedSenders.getByRole("button", { name: "Add" }).click();
    await expect(watchedSenders.getByText("bob@example.com")).toBeVisible();

    await watchedSenders.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Saved.")).toBeVisible();

    const stored = await readWatchList(request, uid);
    expect(stored).toContain("bob@example.com");
  });
});
