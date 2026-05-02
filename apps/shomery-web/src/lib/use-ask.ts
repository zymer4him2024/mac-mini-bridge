"use client";

import { useCallback, useState } from "react";

import { useAuth } from "@/lib/firebase/auth";

export interface AskMeta {
  error: string | null;
  hits: number;
  relevant: number;
  top_dist: number;
}

export type AskStatus = "idle" | "loading" | "success" | "error";

export interface AskResult {
  question: string;
  reply: string;
  meta: AskMeta;
}

interface UseAskState {
  status: AskStatus;
  last: AskResult | null;
  errorMessage: string | null;
}

export interface UseAsk {
  status: AskStatus;
  last: AskResult | null;
  errorMessage: string | null;
  ask: (question: string) => Promise<void>;
  reset: () => void;
}

const INITIAL: UseAskState = {
  status: "idle",
  last: null,
  errorMessage: null,
};

export function useAsk(slug: string, subjectDisplay: string): UseAsk {
  const { user, status: authStatus } = useAuth();
  const [state, setState] = useState<UseAskState>(INITIAL);

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed) return;
      if (authStatus !== "signed-in" || !user) {
        setState({ status: "error", last: null, errorMessage: "not-signed-in" });
        return;
      }
      const baseUrl = process.env.NEXT_PUBLIC_RAG_BASE_URL;
      if (!baseUrl) {
        setState({ status: "error", last: null, errorMessage: "rag-not-configured" });
        return;
      }
      setState((prev) => ({ ...prev, status: "loading", errorMessage: null }));
      try {
        const token = await user.getIdToken();
        const res = await fetch(`${baseUrl.replace(/\/$/, "")}/ask`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            question: trimmed,
            subject_slug: slug,
            subject_display: subjectDisplay,
          }),
        });
        if (!res.ok) {
          setState({
            status: "error",
            last: null,
            errorMessage: `http-${res.status}`,
          });
          return;
        }
        const body = (await res.json()) as { reply: string; meta: AskMeta };
        setState({
          status: "success",
          last: { question: trimmed, reply: body.reply, meta: body.meta },
          errorMessage: null,
        });
      } catch (err) {
        setState({
          status: "error",
          last: null,
          errorMessage: err instanceof Error ? err.message : "fetch-failed",
        });
      }
    },
    [authStatus, user, slug, subjectDisplay],
  );

  const reset = useCallback(() => setState(INITIAL), []);

  return {
    status: state.status,
    last: state.last,
    errorMessage: state.errorMessage,
    ask,
    reset,
  };
}
