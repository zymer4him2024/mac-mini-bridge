/**
 * End-to-end Settings → Notifications flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because the test
 * needs both the Firebase Auth emulator (for anonymous sign-in) and the
 * Firestore emulator (to verify the post-save state).
 *
 * To run locally:
 *   1. Start the Firebase Emulator Suite: `pnpm shomery:emulators`
 *   2. Start the dev server with emulator wiring on:
 *      `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm shomery:dev`
 *   3. Run: `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm --filter shomery-web test:e2e tests/e2e/notifications-settings.spec.ts`
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";

interface FirestoreDoc {
  fields?: {
    digestEnabled?: { booleanValue?: boolean };
    telegramEnabled?: { booleanValue?: boolean };
    telegramChatId?: { stringValue?: string };
  };
}

async function readConfig(
  request: APIRequestContext,
  uid: string,
): Promise<FirestoreDoc> {
  const url = `${FIRESTORE_HOST}/v1/projects/${PROJECT_ID}/databases/(default)/documents/users/${uid}/config/main`;
  const res = await request.get(url, {
    headers: { Authorization: "Bearer owner" },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to read config for ${uid}: ${res.status()} ${await res.text()}`,
    );
  }
  return (await res.json()) as FirestoreDoc;
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

test.describe("settings → notifications flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );

  test("a signed-in user can toggle digest, save, and the change persists; Telegram shows as Coming soon", async ({
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

    await page
      .getByRole("switch", { name: "Disable Email digest" })
      .click();

    await page.getByRole("button", { name: "Save" }).last().click();
    await expect(page.getByText("Saved.")).toBeVisible();

    const stored = await readConfig(request, uid);
    expect(stored.fields?.digestEnabled?.booleanValue).toBe(false);

    // Telegram is demoted to Coming soon during pilot — switch is disabled
    // and there is no Chat ID input on the page.
    await expect(
      page.getByRole("switch", { name: "Telegram" }),
    ).toBeDisabled();
    await expect(page.getByLabel("Chat ID")).toHaveCount(0);
  });
});
