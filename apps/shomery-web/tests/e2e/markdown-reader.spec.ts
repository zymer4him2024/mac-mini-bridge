/**
 * End-to-end markdown reader flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because the test
 * needs the Auth, Firestore, and Storage emulators (anon sign-in + seed data
 * + .md fixture upload).
 *
 * Storage uploads use the emulator's privileged `Bearer owner` token to write
 * the fixture (Storage rules deny writes from any web client; the Python
 * pipeline uses the admin SDK in production).
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";
const STORAGE_HOST = "http://localhost:9199";
const BUCKET = `${PROJECT_ID}.appspot.com`;

const FIXTURE_MD = `# Acme deal — summary

The vendor is Acme Inc.

## Key points

- Term sheet attached
- Sign by Friday

## Action

Reply with the signed PDF.
`;

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

async function uploadFixture(
  request: APIRequestContext,
  objectPath: string,
  body: string,
): Promise<void> {
  const url = `${STORAGE_HOST}/upload/storage/v1/b/${BUCKET}/o?name=${encodeURIComponent(
    objectPath,
  )}&uploadType=media`;
  const res = await request.post(url, {
    headers: {
      Authorization: "Bearer owner",
      "Content-Type": "text/markdown",
    },
    data: body,
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to upload ${objectPath}: ${res.status()} ${await res.text()}`,
    );
  }
}

test.describe("markdown reader flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore + Storage emulators",
  );

  test("a signed-in user can open the per-item page and see rendered markdown", async ({
    page,
    request,
  }) => {
    await page.goto("/en/sign-in");

    await page.waitForFunction(() => !!window.__shomeryE2E);
    const uid = await page.evaluate(() =>
      window.__shomeryE2E!.signInAnonymously(),
    );

    const markdownPath = `summaries/${uid}/acme/abc123.md`;

    await Promise.all([
      writeDoc(request, `users/${uid}`, {
        onboardingCompletedAt: { timestampValue: new Date().toISOString() },
      }),
      writeDoc(request, `users/${uid}/folders/acme`, {
        subject: { stringValue: "Acme deal" },
        subjectSlug: { stringValue: "acme" },
        folderPath: { stringValue: "/acme" },
        pdfCount: { integerValue: 1 },
        hasSummaryCsv: { booleanValue: false },
        createdAt: { timestampValue: new Date().toISOString() },
        updatedAt: { timestampValue: new Date().toISOString() },
      }),
      writeDoc(request, `users/${uid}/folders/acme/items/abc123`, {
        uid: { stringValue: uid },
        folderSubject: { stringValue: "Acme deal" },
        folderSlug: { stringValue: "acme" },
        date: { stringValue: "2026-04-29" },
        from: { stringValue: "Acme Sender <sales@acme.test>" },
        urgency: { stringValue: "low" },
        keyPoints: { arrayValue: { values: [{ stringValue: "Seeded" }] } },
        asks: { arrayValue: { values: [] } },
        suggestedResponse: { stringValue: "" },
        pdfFilename: { stringValue: "" },
        markdownStoragePath: { stringValue: markdownPath },
        createdAt: { timestampValue: new Date().toISOString() },
      }),
      uploadFixture(request, markdownPath, FIXTURE_MD),
    ]);

    await expect(page).toHaveURL(/\/en\/feed$/, { timeout: 15_000 });

    await page.goto(`/en/subjects/acme/items/abc123`);

    await expect(
      page.getByRole("heading", { name: "Acme deal — summary" }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByRole("heading", { name: "Key points" }),
    ).toBeVisible();
    await expect(page.getByText("Term sheet attached")).toBeVisible();
    await expect(page.getByText("Sign by Friday")).toBeVisible();
  });
});
