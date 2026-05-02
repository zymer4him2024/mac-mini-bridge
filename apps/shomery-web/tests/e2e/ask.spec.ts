/**
 * End-to-end Ask flow.
 *
 * The browser hits a mocked rag_service /ask endpoint via Playwright's route
 * interception, so this test does not require a live Mac Mini / Ollama. We
 * still need the Firebase Auth + Firestore emulators for the anon sign-in
 * + folder seeding the route page reads on mount.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";
const RAG_BASE_URL = "https://rag.example.test";

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

test.describe("ask flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );
  test.skip(
    process.env.NEXT_PUBLIC_RAG_BASE_URL !== RAG_BASE_URL,
    `NEXT_PUBLIC_RAG_BASE_URL must be set to ${RAG_BASE_URL} for this spec to intercept correctly`,
  );

  test("user navigates from subject detail → ask page → submits a question and sees the reply", async ({
    page,
    request,
  }) => {
    await page.route(`${RAG_BASE_URL}/ask`, async (route) => {
      const body = route.request().postDataJSON() as {
        question: string;
        subject_slug: string;
        subject_display: string;
      };
      expect(body.subject_slug).toBe("acme");
      expect(body.subject_display).toBe("Acme deal");
      expect(body.question).toBe("What did Acme say about budget?");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          reply: "Acme is targeting a **$40k** pilot.",
          meta: { error: null, hits: 5, relevant: 3, top_dist: 0.42 },
        }),
      });
    });

    await page.goto("/en/sign-in");
    await page.waitForFunction(() => !!window.__shomeryE2E);
    const uid = await page.evaluate(() =>
      window.__shomeryE2E!.signInAnonymously(),
    );

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
        keyPoints: {
          arrayValue: { values: [{ stringValue: "Budget approved" }] },
        },
        asks: { arrayValue: { values: [] } },
        suggestedResponse: { stringValue: "" },
        pdfFilename: { stringValue: "" },
        createdAt: { timestampValue: new Date().toISOString() },
      }),
    ]);

    await expect(page).toHaveURL(/\/en\/feed$/, { timeout: 15_000 });

    await page.goto("/en/subjects/acme");
    const cta = page.getByRole("link", { name: "Ask this subject" });
    await expect(cta).toBeVisible({ timeout: 10_000 });
    await cta.click();

    await expect(page).toHaveURL(/\/en\/subjects\/acme\/ask$/);
    await expect(
      page.getByRole("heading", { name: "Ask Acme deal" }),
    ).toBeVisible();
    await expect(page.getByText("Budget approved")).toBeVisible();

    await page
      .getByPlaceholder("Ask anything about this subject…")
      .fill("What did Acme say about budget?");
    await page.getByRole("button", { name: "Ask" }).click();

    await expect(page.getByText("$40k")).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText("Found 5 candidates · 3 relevant"),
    ).toBeVisible();
  });
});
