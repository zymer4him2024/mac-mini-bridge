/**
 * Shomery Firestore security-rules tests.
 *
 * Schema: users/{uid} (identity) + /config/main + /folders/{slug}/items/{id} + /secrets/*.
 * Web client may only write identity fields on its own users/{uid} doc.
 * Python pipeline (admin SDK) writes folders/items/secrets bypassing rules.
 *
 * Boots its own emulator via the test harness or relies on `firebase emulators:exec`.
 * The test is skipped when no Firestore emulator is reachable so suites running
 * outside the emulator wrapper don't spuriously fail.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

const emulatorAvailable =
  process.env.FIRESTORE_EMULATOR_HOST !== undefined ||
  process.env.FIREBASE_EMULATOR_HUB !== undefined;

const describeIf = emulatorAvailable ? describe : describe.skip;

describeIf("Firestore security rules — Shomery", () => {
  let testEnv: import("@firebase/rules-unit-testing").RulesTestEnvironment;

  beforeAll(async () => {
    const { initializeTestEnvironment } = await import(
      "@firebase/rules-unit-testing"
    );
    testEnv = await initializeTestEnvironment({
      projectId: "shomery-rules-test",
      firestore: {
        rules: readFileSync(
          path.resolve(__dirname, "../../firestore.rules"),
          "utf8",
        ),
      },
    });
  });

  afterEach(async () => {
    if (testEnv) await testEnv.clearFirestore();
  });

  afterAll(async () => {
    if (testEnv) await testEnv.cleanup();
  });

  describe("identity doc — users/{uid}", () => {
    it("allows owner to create with only identity fields", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(doc(alice, "users/alice"), {
          email: "alice@example.com",
          displayName: "Alice",
          photoURL: "https://example.com/a.png",
          createdAt: serverTimestamp(),
          lastSignedInAt: serverTimestamp(),
        }),
      );
    });

    it("denies a foreign uid from writing another user's identity", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      const bob = testEnv.authenticatedContext("bob").firestore();
      await assertFails(
        setDoc(doc(bob, "users/alice"), {
          email: "alice@example.com",
          displayName: "Alice",
          photoURL: "",
          createdAt: serverTimestamp(),
          lastSignedInAt: serverTimestamp(),
        }),
      );
    });

    it("denies create with a non-allowlisted field", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(doc(alice, "users/alice"), {
          email: "alice@example.com",
          displayName: "Alice",
          photoURL: "",
          createdAt: serverTimestamp(),
          lastSignedInAt: serverTimestamp(),
          gmail: { refreshToken: "stolen" },
        }),
      );
    });

    it("denies update touching a non-allowlisted field", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice"), {
          email: "alice@example.com",
          displayName: "Alice",
          photoURL: "",
          createdAt: serverTimestamp(),
          lastSignedInAt: serverTimestamp(),
          gmail: { email: "alice@example.com" },
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(
          doc(alice, "users/alice"),
          { gmail: { refreshToken: "stolen" } },
          { merge: true },
        ),
      );
    });

    it("allows owner to set onboardingCompletedAt via merge update", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice"), {
          email: "alice@example.com",
          displayName: "Alice",
          photoURL: "",
          createdAt: serverTimestamp(),
          lastSignedInAt: serverTimestamp(),
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(
          doc(alice, "users/alice"),
          { onboardingCompletedAt: serverTimestamp() },
          { merge: true },
        ),
      );
    });

    it("allows owner to create with onboardingCompletedAt alongside identity fields", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(doc(alice, "users/alice"), {
          email: "alice@example.com",
          displayName: "Alice",
          photoURL: "",
          createdAt: serverTimestamp(),
          lastSignedInAt: serverTimestamp(),
          onboardingCompletedAt: serverTimestamp(),
        }),
      );
    });
  });

  describe("folder items — collection-group reads", () => {
    it("allows owner to read their own item", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, getDoc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(
          doc(ctx.firestore(), "users/alice/folders/acme/items/2024-12-15-acme"),
          {
            uid: "alice",
            folderSubject: "Acme deal",
            folderSlug: "acme",
            date: "2024-12-15",
            from: "Acme <deals@acme.com>",
            urgency: "high",
            keyPoints: ["term-sheet attached"],
            asks: ["sign by Friday"],
            suggestedResponse: "review w/ legal",
            pdfFilename: "acme.pdf",
            createdAt: serverTimestamp(),
          },
        );
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        getDoc(
          doc(alice, "users/alice/folders/acme/items/2024-12-15-acme"),
        ),
      );
    });

    it("denies a foreign uid from reading another user's item", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, getDoc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(
          doc(ctx.firestore(), "users/alice/folders/acme/items/foreign-read"),
          {
            uid: "alice",
            folderSubject: "Acme",
            folderSlug: "acme",
            date: "",
            from: "",
            urgency: "low",
            keyPoints: [],
            asks: [],
            suggestedResponse: "",
            pdfFilename: "",
            createdAt: serverTimestamp(),
          },
        );
      });

      const bob = testEnv.authenticatedContext("bob").firestore();
      await assertFails(
        getDoc(
          doc(bob, "users/alice/folders/acme/items/foreign-read"),
        ),
      );
    });

    it("denies any client write to an item", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, serverTimestamp } = await import(
        "firebase/firestore"
      );

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(
          doc(alice, "users/alice/folders/acme/items/client-write"),
          {
            uid: "alice",
            folderSubject: "Acme",
            folderSlug: "acme",
            date: "",
            from: "",
            urgency: "low",
            keyPoints: [],
            asks: [],
            suggestedResponse: "",
            pdfFilename: "",
            createdAt: serverTimestamp(),
          },
        ),
      );
    });
  });

  describe("secrets subcollection", () => {
    it("denies the owner from reading their own secrets", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, getDoc } = await import("firebase/firestore");

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice/secrets/gmail"), {
          refreshToken: "kms-wrapped-blob",
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        getDoc(doc(alice, "users/alice/secrets/gmail")),
      );
    });
  });

  describe("config subcollection", () => {
    it("allows the owner to read their config", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc, getDoc } = await import("firebase/firestore");

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
          digestEnabled: true,
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        getDoc(doc(alice, "users/alice/config/main")),
      );
    });

    it("allows the owner to create config/main with only priorityWatchSenders", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(doc(alice, "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com", "deals@vendor.io"],
        }),
      );
    });

    it("allows the owner to update priorityWatchSenders on an existing config doc", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
          digestEnabled: true,
          retentionDays: 30,
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(
          doc(alice, "users/alice/config/main"),
          { priorityWatchSenders: ["@acme.com", "@vendor.io"] },
          { merge: true },
        ),
      );
    });

    it("denies a non-owner from writing priorityWatchSenders", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const bob = testEnv.authenticatedContext("bob").firestore();
      await assertFails(
        setDoc(doc(bob, "users/alice/config/main"), {
          priorityWatchSenders: ["@evil.com"],
        }),
      );
    });

    it("allows create that includes digestEnabled alongside priorityWatchSenders", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(doc(alice, "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
          digestEnabled: true,
        }),
      );
    });

    it("allows merge-update of digestEnabled on an existing config doc", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
          digestEnabled: true,
          retentionDays: 30,
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(
          doc(alice, "users/alice/config/main"),
          { digestEnabled: false },
          { merge: true },
        ),
      );
    });

    it("denies update that touches a non-allowlisted field", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
          retentionDays: 30,
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(
          doc(alice, "users/alice/config/main"),
          { retentionDays: 60 },
          { merge: true },
        ),
      );
    });

    it("allows merge-update of telegramEnabled + telegramChatId together", async () => {
      const { assertSucceeds } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertSucceeds(
        setDoc(
          doc(alice, "users/alice/config/main"),
          { telegramEnabled: true, telegramChatId: "123456789" },
          { merge: true },
        ),
      );
    });

    it("denies enabling Telegram with an empty chat id", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      await testEnv.withSecurityRulesDisabled(async (ctx) => {
        await setDoc(doc(ctx.firestore(), "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
        });
      });

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(
          doc(alice, "users/alice/config/main"),
          { telegramEnabled: true, telegramChatId: "" },
          { merge: true },
        ),
      );
    });

    it("denies a non-boolean digestEnabled", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(doc(alice, "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
          digestEnabled: "yes",
        }),
      );
    });

    it("denies a telegramChatId longer than 64 characters", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(doc(alice, "users/alice/config/main"), {
          priorityWatchSenders: ["@acme.com"],
          telegramEnabled: true,
          telegramChatId: "x".repeat(65),
        }),
      );
    });

    it("denies a watch list with a non-list value", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(doc(alice, "users/alice/config/main"), {
          priorityWatchSenders: "not-a-list",
        }),
      );
    });

    it("denies a watch list larger than 200 entries", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const oversize = Array.from({ length: 201 }, (_, i) => `n${i}@x.com`);
      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(doc(alice, "users/alice/config/main"), {
          priorityWatchSenders: oversize,
        }),
      );
    });

    it("denies non-main config docs even from the owner", async () => {
      const { assertFails } = await import("@firebase/rules-unit-testing");
      const { setDoc, doc } = await import("firebase/firestore");

      const alice = testEnv.authenticatedContext("alice").firestore();
      await assertFails(
        setDoc(doc(alice, "users/alice/config/sneaky"), {
          priorityWatchSenders: ["@acme.com"],
        }),
      );
    });
  });
});
