/**
 * End-to-end Subject Groups flow.
 *
 * Skipped when `NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true"` because the test
 * needs both the Firebase Auth emulator (for anonymous sign-in) and the
 * Firestore emulator (to seed folders and read the resulting groups doc).
 *
 * Seeding bypasses security rules using the Firestore emulator's `Bearer owner`
 * privileged token — this only works against the local emulator and never
 * touches production.
 *
 * To run locally:
 *   1. Start the Firebase Emulator Suite: `pnpm shomery:emulators`
 *   2. Start the dev server with emulator wiring on:
 *      `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm shomery:dev`
 *   3. Run: `NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true pnpm --filter shomery-web test:e2e tests/e2e/groups.spec.ts`
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT_ID =
  process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "shomery-emulator";
const FIRESTORE_HOST = "http://localhost:8080";

interface FolderSeed {
  subject: string;
  subjectSlug: string;
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

interface GroupListResponse {
  documents?: { name: string; fields?: Record<string, unknown> }[];
}

async function listGroups(
  request: APIRequestContext,
  uid: string,
): Promise<GroupListResponse> {
  const url = `${FIRESTORE_HOST}/v1/projects/${PROJECT_ID}/databases/(default)/documents/users/${uid}/groups`;
  const res = await request.get(url, {
    headers: { Authorization: "Bearer owner" },
  });
  if (!res.ok() && res.status() !== 404) {
    throw new Error(
      `Failed to list groups for ${uid}: ${res.status()} ${await res.text()}`,
    );
  }
  if (res.status() === 404) return {};
  return (await res.json()) as GroupListResponse;
}

function folderFields(seed: FolderSeed): Record<string, unknown> {
  const now = new Date().toISOString();
  return {
    subject: { stringValue: seed.subject },
    subjectSlug: { stringValue: seed.subjectSlug },
    folderPath: { stringValue: `/${seed.subjectSlug}` },
    pdfCount: { integerValue: 1 },
    hasSummaryCsv: { booleanValue: false },
    createdAt: { timestampValue: now },
    updatedAt: { timestampValue: now },
  };
}

test.describe("subject groups flow", () => {
  test.skip(
    process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true",
    "Requires Firebase Auth + Firestore emulators",
  );

  test("a signed-in user can create a group, add subjects, see them in the sidebar, rename, and delete", async ({
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
        folderFields({ subject: "Acme deal", subjectSlug: "acme" }),
      ),
      writeDoc(
        request,
        `users/${uid}/folders/okrs`,
        folderFields({ subject: "Q4 OKRs", subjectSlug: "okrs" }),
      ),
    ]);

    await expect(page).toHaveURL(/\/en\/feed$/, { timeout: 15_000 });

    await page.goto("/en/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

    const section = page.locator('section[aria-labelledby="groups-heading"]');
    await expect(
      section.getByRole("heading", { name: "Subject groups" }),
    ).toBeVisible();

    // Create a group named "Clients".
    await section.getByLabel("New group name").fill("Clients");
    await section.getByRole("button", { name: "Add group" }).click();

    await expect(
      section.getByRole("button", { name: /^Clients/ }),
    ).toBeVisible();

    // Add both subjects to the group.
    await section.getByRole("button", { name: "Edit members" }).click();
    await section.getByLabel("Acme deal").check();
    await section.getByLabel("Q4 OKRs").check();
    await section.getByRole("button", { name: "Save" }).click();

    await expect(section.getByText("2 subjects")).toBeVisible();

    // Sidebar shows the group with both members nested.
    await page.goto("/en/feed");
    await expect(
      page.getByRole("button", { name: "Collapse Clients" }),
    ).toBeVisible({ timeout: 10_000 });

    // Rename the group.
    await page.goto("/en/settings");
    await section.getByRole("button", { name: /^Clients/ }).click();
    const renameInput = section.getByLabel("Group name", { exact: true });
    await renameInput.fill("VIP Clients");
    await section.getByRole("button", { name: "Save" }).click();
    await expect(
      section.getByRole("button", { name: /^VIP Clients/ }),
    ).toBeVisible();

    // Verify the rename persisted.
    const after = await listGroups(request, uid);
    const renamed = after.documents?.find(
      (d) =>
        (d.fields as { name?: { stringValue?: string } } | undefined)?.name
          ?.stringValue === "VIP Clients",
    );
    expect(renamed).toBeTruthy();

    // Delete the group.
    await section.getByRole("button", { name: "Delete" }).click();
    await section.getByLabel("Confirmation phrase").fill("VIP Clients");
    await section.getByRole("button", { name: "Delete group" }).click();

    await expect(
      section.getByText(
        "You don't have any groups yet. Create one to bundle related subjects.",
      ),
    ).toBeVisible();
  });
});
