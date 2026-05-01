import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const askMock = vi.fn();
const useAskMock = vi.fn();

vi.mock("@/lib/use-ask", () => ({
  useAsk: () => useAskMock(),
}));

import { AskPanel } from "@/components/subjects/ask-panel";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

interface HookOverrides {
  status?: "idle" | "loading" | "success" | "error";
  last?: {
    question: string;
    reply: string;
    meta: {
      error: string | null;
      hits: number;
      relevant: number;
      top_dist: number;
    };
  } | null;
  errorMessage?: string | null;
}

function setHookState(state: HookOverrides = {}) {
  useAskMock.mockReturnValue({
    status: "idle",
    last: null,
    errorMessage: null,
    ask: askMock,
    reset: vi.fn(),
    ...state,
  });
}

describe("AskPanel", () => {
  beforeEach(() => {
    askMock.mockReset();
    useAskMock.mockReset();
    setHookState();
  });

  it("disables submit when the input is empty", () => {
    render(withIntl(<AskPanel slug="acme" subjectDisplay="Acme deal" />));
    const submit = screen.getByRole("button", { name: "Ask" });
    expect(submit).toBeDisabled();
  });

  it("calls ask() with the trimmed question on submit", async () => {
    const user = userEvent.setup();
    render(withIntl(<AskPanel slug="acme" subjectDisplay="Acme deal" />));
    await user.type(
      screen.getByPlaceholderText("Ask anything about this subject…"),
      "  What about budget?  ",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect(askMock).toHaveBeenCalledWith("What about budget?");
  });

  it("renders loading state while the request is in flight", () => {
    setHookState({ status: "loading" });
    render(withIntl(<AskPanel slug="acme" subjectDisplay="Acme deal" />));
    expect(
      screen.getByRole("button", { name: "Thinking…" }),
    ).toBeDisabled();
    expect(screen.getByText("Searching this subject…")).toBeInTheDocument();
  });

  it("renders the last reply with question + answer + meta", () => {
    setHookState({
      status: "success",
      last: {
        question: "Anything about budget?",
        reply: "Acme is targeting **$40k**.",
        meta: { error: null, hits: 5, relevant: 3, top_dist: 0.42 },
      },
    });
    render(withIntl(<AskPanel slug="acme" subjectDisplay="Acme deal" />));
    expect(screen.getByText("Anything about budget?")).toBeInTheDocument();
    expect(screen.getByText("$40k")).toBeInTheDocument();
    expect(
      screen.getByText("Found 5 candidates · 3 relevant"),
    ).toBeInTheDocument();
  });

  it("maps known error codes to localized strings", () => {
    setHookState({ status: "error", errorMessage: "rag-not-configured" });
    render(withIntl(<AskPanel slug="acme" subjectDisplay="Acme deal" />));
    expect(
      screen.getByText(
        "Ask isn't connected yet. Set NEXT_PUBLIC_RAG_BASE_URL in your environment.",
      ),
    ).toBeInTheDocument();
  });

  it("falls back to a generic error message for unknown codes", () => {
    setHookState({ status: "error", errorMessage: "http-500" });
    render(withIntl(<AskPanel slug="acme" subjectDisplay="Acme deal" />));
    expect(
      screen.getByText("We couldn't reach the assistant. Please try again."),
    ).toBeInTheDocument();
  });
});
