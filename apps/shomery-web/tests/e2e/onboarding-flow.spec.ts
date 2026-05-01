/**
 * End-to-end onboarding completion flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because the test
 * needs both the Firebase Auth emulator (anonymous sign-in) and the Firestore
 * emulator (to verify onboardingCompletedAt and the persisted watch list).
 *
 * Verification reads use the Firestore emulator's `Bearer owner` privileged
 * token — local-only, never touches production.
 *
 * To run locally:
 *   1. Start the Firebase Emulator Suite: `pnpm shomery:emulators`
 *   2. Start the dev server with emulator wiring on:
 *      `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm shomery:dev`
 *   3. Run: `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm --filter shomery-web test:e2e tests/e2e/onboarding-flow.spec.ts`
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";

interface UserDoc {
  fields?: {
    onboardingCompletedAt?: { timestampValue?: string };
  };
}

async function readUser(
  request: APIRequestContext,
  uid: string,
): Promise<UserDoc> {
  const url = `${FIRESTORE_HOST}/v1/projects/${PROJECT_ID}/databases/(default)/documents/users/${uid}`;
  const res = await request.get(url, {
    headers: { Authorization: "Bearer owner" },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to read user ${uid}: ${res.status()} ${await res.text()}`,
    );
  }
  return (await res.json()) as UserDoc;
}

test.describe("onboarding completion flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );

  test("a fresh user walks the 3 steps and lands on /feed", async ({
    page,
    request,
  }) => {
    await page.goto("/en/sign-in");

    await page.waitForFunction(() => !!window.__shomeryE2E);
    const uid = await page.evaluate(() =>
      window.__shomeryE2E!.signInAnonymously(),
    );

    await expect(page).toHaveURL(/\/en\/onboarding$/);
    await expect(
      page.getByRole("heading", { name: "Welcome to Shomery." }),
    ).toBeVisible();

    await page.getByRole("link", { name: "Get started" }).click();
    await expect(page).toHaveURL(/\/en\/onboarding\/connect$/);

    await page.getByRole("link", { name: "Continue" }).click();
    await expect(page).toHaveURL(/\/en\/onboarding\/watch$/);

    await page
      .getByPlaceholder("alice@example.com or @acme.com")
      .fill("alice@example.com");
    await page.getByRole("button", { name: "Add" }).click();
    await expect(page.getByText("alice@example.com")).toBeVisible();
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page).toHaveURL(/\/en\/onboarding\/save$/);

    await page.getByRole("button", { name: "Start watching" }).click();
    await expect(page).toHaveURL(/\/en\/feed$/);

    const userDoc = await readUser(request, uid);
    expect(userDoc.fields?.onboardingCompletedAt?.timestampValue).toBeTruthy();
  });
});
