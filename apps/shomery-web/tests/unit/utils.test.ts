import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("joins simple class strings", () => {
    expect(cn("a", "b", "c")).toBe("a b c");
  });

  it("filters out falsy values", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b");
  });

  it("merges conflicting Tailwind utilities so the last one wins", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });

  it("preserves non-conflicting utilities", () => {
    expect(cn("p-2", "m-4")).toBe("p-2 m-4");
  });

  it("supports the conditional-object form from clsx", () => {
    expect(cn({ "is-active": true, "is-hidden": false })).toBe("is-active");
  });
});
