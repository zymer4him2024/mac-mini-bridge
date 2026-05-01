import { beforeEach, describe, expect, it, vi } from "vitest";

const callableMock = vi.fn();
const httpsCallableFactory = vi.fn(
  (_instance: unknown, _name: string) => callableMock,
);

vi.mock("firebase/functions", () => ({
  httpsCallable: (instance: unknown, name: string) =>
    httpsCallableFactory(instance, name),
}));

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseFunctions: () => ({ name: "fn-instance" }),
}));

import { callDeleteAccount } from "@/lib/account-delete";

describe("callDeleteAccount", () => {
  beforeEach(() => {
    callableMock.mockReset();
    httpsCallableFactory.mockClear();
  });

  it("invokes the deleteAccount callable and resolves on success", async () => {
    callableMock.mockResolvedValue({ data: { success: true } });
    await expect(callDeleteAccount()).resolves.toBeUndefined();
    expect(httpsCallableFactory).toHaveBeenCalledWith(
      { name: "fn-instance" },
      "deleteAccount",
    );
    expect(callableMock).toHaveBeenCalledWith({});
  });

  it("throws when the function returns failure", async () => {
    callableMock.mockResolvedValue({ data: { success: false } });
    await expect(callDeleteAccount()).rejects.toThrow(
      /returned failure/,
    );
  });

  it("propagates errors thrown by the callable", async () => {
    callableMock.mockRejectedValue(new Error("permission-denied"));
    await expect(callDeleteAccount()).rejects.toThrow("permission-denied");
  });
});
