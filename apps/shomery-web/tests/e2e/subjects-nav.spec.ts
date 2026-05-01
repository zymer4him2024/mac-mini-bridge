/**
 * End-to-end Subjects sidebar + per-subject detail flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because the test
 * needs both the Firebase Auth emulator (for anonymous sign-in) and the
 * Firestore emulator (for seeding folder docs via the emulator REST API).
 *
 * Seeding bypasses security rules using the Firestore emulator's `Bearer owner`
 * privileged token — this only works against the local emulator and never
 * touches production.
 *
 * To run locally:
 *   1. Start the Firebase Emulator Suite: `pnpm shomery:emulators`
 *   2. Start the dev server with emulator wiring on:
 *      `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm shomery:dev`
 *   3. Run: `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm --filter shomery-web test:e2e tests/e2e/subjects-nav.spec.ts`
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";

interface FolderSeed {
  subject: string;
  subjectSlug: string;
  pdfCount: number;
}

interface ItemSeed {
  uid: string;
  folderSubject: string;
  folderSlug: string;
  from: string;
  pdfFilename: string;
}

async function writeDoc(
  request: APIRequestContext,
  documentPath: string,
  fields: Record<string, unknown>,
): Promise<void> {
  const url = `${FIRESTORE_HOST}/v1/projects/${PROJECT_ID}/databases/(default)/documents/${documentPath}`;
  const res = await request.patch(url, {
    headers: { Authorization: "Bearer owner" },
    data: { fields },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to seed ${documentPath}: ${res.status()} ${await res.text()}`,
    );
  }
}

function folderFields(seed: FolderSeed): Record<string, unknown> {
  const now = new Date().toISOString();
  return {
    subject: { stringValue: seed.subject },
    subjectSlug: { stringValue: seed.subjectSlug },
    folderPath: { stringValue: `/${seed.subjectSlug}` },
    pdfCount: { integerValue: seed.pdfCount },
    hasSummaryCsv: { booleanValue: false },
    createdAt: { timestampValue: now },
    updatedAt: { timestampValue: now },
  };
}

function itemFields(seed: ItemSeed): Record<string, unknown> {
  const now = new Date().toISOString();
  return {
    uid: { stringValue: seed.uid },
    folderSubject: { stringValue: seed.folderSubject },
    folderSlug: { stringValue: seed.folderSlug },
    date: { stringValue: "2026-04-29" },
    from: { stringValue: seed.from },
    urgency: { stringValue: "low" },
    keyPoints: {
      arrayValue: { values: [{ stringValue: "Seeded for e2e" }] },
    },
    asks: { arrayValue: { values: [] } },
    suggestedResponse: { stringValue: "" },
    pdfFilename: { stringValue: seed.pdfFilename },
    createdAt: { timestampValue: now },
  };
}

test.describe("subjects sidebar + detail flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );

  test("seeded folders appear in the sidebar; clicking one navigates to detail", async ({
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
      }),
      writeDoc(
        request,
        `users/${uid}/folders/acme`,
        folderFields({ subject: "Acme deal", subjectSlug: "acme", pdfCount: 1 }),
      ),
      writeDoc(
        request,
        `users/${uid}/folders/okrs`,
        folderFields({ subject: "Q4 OKRs", subjectSlug: "okrs", pdfCount: 1 }),
      ),
      writeDoc(
        request,
        `users/${uid}/folders/acme/items/itm-acme-1`,
        itemFields({
          uid,
          folderSubject: "Acme deal",
          folderSlug: "acme",
          from: "Acme Sender <sales@acme.test>",
          pdfFilename: "acme-1.pdf",
        }),
      ),
      writeDoc(
        request,
        `users/${uid}/folders/okrs/items/itm-okrs-1`,
        itemFields({
          uid,
          folderSubject: "Q4 OKRs",
          folderSlug: "okrs",
          from: "OKR Sender <okrs@example.test>",
          pdfFilename: "okrs-1.pdf",
        }),
      ),
    ]);

    await expect(page).toHaveURL(/\/en\/feed$/, { timeout: 15_000 });
    await expect(page.getByRole("link", { name: "Inbox" })).toBeVisible();

    await expect(page.getByText("Acme deal").first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText("Q4 OKRs").first()).toBeVisible();

    await page.getByRole("link", { name: /Acme deal/ }).first().click();
    await expect(page).toHaveURL(/\/en\/subjects\/acme$/);
    await expect(
      page.getByText("Acme Sender <sales@acme.test>"),
    ).toBeVisible();
  });
});
