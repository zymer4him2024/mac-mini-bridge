/**
 * End-to-end Settings → Privacy & data export flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because the test
 * needs the Firebase Auth + Firestore emulators (anon sign-in + seed data).
 *
 * The delete flow is intentionally not exercised end-to-end here because the
 * functions emulator is not part of the current `test:e2e:emulators` wrap.
 * Coverage for the delete path lives in the unit tests
 * (`tests/unit/account-delete.test.ts` and the editor spec).
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";

async function writeDoc(
  request: APIRequestContext,
  path: string,
  fields: Record<string, unknown>,
): Promise<void> {
  const url = `${FIRESTORE_HOST}/v1/projects/${PROJECT_ID}/databases/(default)/documents/${path}`;
  const res = await request.patch(url, {
    headers: { Authorization: "Bearer owner" },
    data: { fields },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to write ${path}: ${res.status()} ${await res.text()}`,
    );
  }
}

test.describe("settings → privacy export flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );

  test("a signed-in user can download a JSON export of their data", async ({
    page,
    request,
  }) => {
    await page.goto("/en/sign-in");

    await page.waitForFunction(() => !!window.__shomeryE2E);
    const uid = await page.evaluate(() =>
      window.__shomeryE2E!.signInAnonymously(),
    );

    await Promise.all([
      writeDoc(request, `users/${uid}`, {
        onboardingCompletedAt: { timestampValue: new Date().toISOString() },
        email: { stringValue: "alice@example.com" },
      }),
      writeDoc(request, `users/${uid}/config/main`, {
        priorityWatchSenders: {
          arrayValue: { values: [{ stringValue: "@acme.com" }] },
        },
      }),
    ]);

    await expect(page).toHaveURL(/\/en\/feed$/, { timeout: 15_000 });
    await page.goto("/en/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    const privacy = page.getByRole("region", { name: "Privacy & data" });

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      privacy.getByRole("button", { name: "Download export" }).click(),
    ]);

    expect(download.suggestedFilename()).toMatch(
      new RegExp(`^shomery-export-${uid}-`),
    );
    await expect(privacy.getByText("Downloaded.")).toBeVisible();
  });
});
