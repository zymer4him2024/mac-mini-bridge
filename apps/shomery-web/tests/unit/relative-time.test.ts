import { describe, expect, it } from "vitest";

import { formatRelativeTime } from "@/lib/intl/relative-time";

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

describe("formatRelativeTime", () => {
  const now = new Date("2026-04-30T12:00:00Z");

  it("formats a moment ago in seconds", () => {
    const target = new Date(now.getTime() - 5 * SECOND);
    expect(formatRelativeTime(target, "en", now)).toMatch(/second/);
  });

  it("formats minutes ago", () => {
    const target = new Date(now.getTime() - 3 * MINUTE);
    expect(formatRelativeTime(target, "en", now)).toMatch(/minute/);
  });

  it("formats hours ago", () => {
    const target = new Date(now.getTime() - 5 * HOUR);
    expect(formatRelativeTime(target, "en", now)).toMatch(/hour/);
  });

  it("formats days ago", () => {
    const target = new Date(now.getTime() - 3 * DAY);
    expect(formatRelativeTime(target, "en", now)).toMatch(/day/);
  });

  it("respects locale", () => {
    const target = new Date(now.getTime() - 3 * DAY);
    const ko = formatRelativeTime(target, "ko", now);
    expect(ko).not.toMatch(/day/);
    expect(ko.length).toBeGreaterThan(0);
  });
});
