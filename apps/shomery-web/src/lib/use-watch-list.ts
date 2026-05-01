"use client";

import { useCallback, useMemo, useState } from "react";

export const MAX_LIST_SIZE = 200;
export const MAX_ENTRY_LENGTH = 255;
export const ENTRY_PATTERN =
  /^(?:@[^\s@]+\.[^\s@]+|[^\s@]+@[^\s@]+\.[^\s@]+|[^\s@]+\.[^\s@]+)$/;

export type ValidationKey =
  | "empty"
  | "duplicate"
  | "tooLong"
  | "invalidFormat"
  | "listFull";

export function normalizeEntries(entries: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of entries) {
    const trimmed = raw.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(trimmed);
  }
  return out;
}

export function validateAddition(
  candidateRaw: string,
  current: string[],
): { error: ValidationKey; value: string } | null {
  const value = candidateRaw.trim();
  if (!value) return { error: "empty", value };
  if (value.length > MAX_ENTRY_LENGTH) return { error: "tooLong", value };
  if (!ENTRY_PATTERN.test(value)) return { error: "invalidFormat", value };
  if (current.length >= MAX_LIST_SIZE) return { error: "listFull", value };
  const lower = value.toLowerCase();
  if (current.some((existing) => existing.toLowerCase() === lower)) {
    return { error: "duplicate", value };
  }
  return null;
}

export interface UseWatchListResult {
  entries: string[];
  baseline: string[];
  draft: string;
  setDraft: (value: string) => void;
  validationError: ValidationKey | null;
  validationValue: string;
  clearValidation: () => void;
  add: () => boolean;
  remove: (value: string) => void;
  reset: (next: string[]) => void;
  dirty: boolean;
}

export function useWatchList(initial: string[]): UseWatchListResult {
  const baseline = useMemo(() => normalizeEntries(initial), [initial]);
  const [entries, setEntries] = useState<string[]>(baseline);
  const [draft, setDraft] = useState("");
  const [validationError, setValidationError] = useState<ValidationKey | null>(
    null,
  );
  const [validationValue, setValidationValue] = useState("");

  const dirty = useMemo(() => {
    if (entries.length !== baseline.length) return true;
    return entries.some((value, idx) => value !== baseline[idx]);
  }, [entries, baseline]);

  const clearValidation = useCallback(() => {
    setValidationError(null);
    setValidationValue("");
  }, []);

  const add = useCallback((): boolean => {
    const result = validateAddition(draft, entries);
    if (result) {
      setValidationError(result.error);
      setValidationValue(result.value);
      return false;
    }
    setEntries((prev) => [...prev, draft.trim()]);
    setDraft("");
    setValidationError(null);
    setValidationValue("");
    return true;
  }, [draft, entries]);

  const remove = useCallback((value: string) => {
    setEntries((prev) => prev.filter((existing) => existing !== value));
  }, []);

  const reset = useCallback((next: string[]) => {
    setEntries(normalizeEntries(next));
    setDraft("");
    setValidationError(null);
    setValidationValue("");
  }, []);

  return {
    entries,
    baseline,
    draft,
    setDraft,
    validationError,
    validationValue,
    clearValidation,
    add,
    remove,
    reset,
    dirty,
  };
}
