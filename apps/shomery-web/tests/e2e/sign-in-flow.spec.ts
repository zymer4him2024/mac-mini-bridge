/**
 * End-to-end auth-routing flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because every
 * branch needs Firebase Auth to bootstrap (signed-out routing checks rely on
 * `onAuthStateChanged` firing with a null user, which only happens when the
 * Auth SDK has a config or emulator host to talk to).
 *
 * To run locally:
 *   1. Start the Firebase Emulator Suite: `pnpm shomery:emulators`
 *   2. Start the dev server with emulator wiring on:
 *      `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm shomery:dev`
 *   3. Run: `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm --filter shomery-web test:e2e tests/e2e/sign-in-flow.spec.ts`
 */
import { expect, test } from "@playwright/test";

test.describe("auth-routing flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );

  test("a signed-out user hitting /en/feed gets bounced to /en/sign-in", async ({
    page,
  }) => {
    await page.goto("/en/feed");
    await expect(page).toHaveURL(/\/en\/sign-in$/);
  });

  test("a signed-in user without onboarding lands on /en/onboarding", async ({
    page,
  }) => {
    await page.goto("/en/sign-in");

    await page.waitForFunction(() => !!window.__shomeryE2E);
    await page.evaluate(() => window.__shomeryE2E!.signInAnonymously());

    await expect(page).toHaveURL(/\/en\/onboarding$/);
    await expect(
      page.getByRole("heading", { name: "Welcome to Shomery." }),
    ).toBeVisible();
  });
});
