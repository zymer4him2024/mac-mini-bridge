/**
 * Shomery Storage security-rules tests.
 *
 * v1 markdown seam — Python pipeline writes summaries (admin SDK, bypasses
 * rules); web reads are scoped to `summaries/{uid}/...` and the web client
 * is never allowed to write.
 *
 * Skipped outside the emulator wrapper so other suites don't spuriously fail.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

const emulatorAvailable =
  process.env.FIREBASE_STORAGE_EMULATOR_HOST !== undefined ||
  process.env.FIREBASE_EMULATOR_HUB !== undefined;

const describeIf = emulatorAvailable ? describe : describe.skip;

describeIf("Storage security rules — Shomery", () => {
  let testEnv: import("@firebase/rules-unit-testing").RulesTestEnvironment;

  beforeAll(async () => {
    const { initializeTestEnvironment } = await import(
      "@firebase/rules-unit-testing"
    );
    testEnv = await initializeTestEnvironment({
      projectId: "shomery-storage-rules-test",
      storage: {
        rules: readFileSync(
          path.resolve(__dirname, "../../storage.rules"),
          "utf8",
        ),
      },
    });
  });

  afterEach(async () => {
    if (testEnv) await testEnv.clearStorage();
  });

  afterAll(async () => {
    if (testEnv) await testEnv.cleanup();
  });

  async function seedAdminFile(filePath: string, text: string): Promise<void> {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      const { ref, uploadString } = await import("firebase/storage");
      await uploadString(ref(ctx.storage(), filePath), text);
    });
  }

  describe("summaries/{uid}/{slug}/{emailId}", () => {
    it("allows the owner to read their own markdown blob", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { getDownloadURL, ref } = await import("firebase/storage");
      await seedAdminFile("summaries/alice/acme/abc.md", "# hello");
      const alice = testEnv.authenticatedContext("alice").storage();
      await assertSucceeds(
        getDownloadURL(ref(alice, "summaries/alice/acme/abc.md")),
      );
    });

    it("denies a different signed-in user reading another user's blob", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { getDownloadURL, ref } = await import("firebase/storage");
      await seedAdminFile("summaries/alice/acme/abc.md", "# hello");
      const bob = testEnv.authenticatedContext("bob").storage();
      await assertFails(
        getDownloadURL(ref(bob, "summaries/alice/acme/abc.md")),
      );
    });

    it("denies anonymous (unauth) reads", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { getDownloadURL, ref } = await import("firebase/storage");
      await seedAdminFile("summaries/alice/acme/abc.md", "# hello");
      const anon = testEnv.unauthenticatedContext().storage();
      await assertFails(
        getDownloadURL(ref(anon, "summaries/alice/acme/abc.md")),
      );
    });

    it("denies the owner writing to their own markdown path (web is read-only)", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { ref, uploadString } = await import("firebase/storage");
      const alice = testEnv.authenticatedContext("alice").storage();
      await assertFails(
        uploadString(ref(alice, "summaries/alice/acme/abc.md"), "# hello"),
      );
    });
  });

  describe("other prefixes", () => {
    it("denies reads outside summaries/{uid}", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { getDownloadURL, ref } = await import("firebase/storage");
      await seedAdminFile("pdfs/alice/abc.pdf", "fake-pdf");
      const alice = testEnv.authenticatedContext("alice").storage();
      await assertFails(getDownloadURL(ref(alice, "pdfs/alice/abc.pdf")));
    });
  });
});
