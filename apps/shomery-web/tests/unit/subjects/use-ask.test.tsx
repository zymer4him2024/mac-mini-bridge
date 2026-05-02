import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const useAuthMock = vi.fn();
vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

import { useAsk } from "@/lib/use-ask";

const ORIGINAL_FETCH = globalThis.fetch;
const ORIGINAL_BASE_URL = process.env.NEXT_PUBLIC_RAG_BASE_URL;

function fakeUser(uid = "alice", token = "fake-id-token") {
  return {
    uid,
    getIdToken: vi.fn().mockResolvedValue(token),
  };
}

describe("useAsk", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    process.env.NEXT_PUBLIC_RAG_BASE_URL = "https://rag.example.com";
  });

  afterEach(() => {
    globalThis.fetch = ORIGINAL_FETCH;
    process.env.NEXT_PUBLIC_RAG_BASE_URL = ORIGINAL_BASE_URL;
  });

  it("starts idle and resolves to a successful reply on the happy path", async () => {
    useAuthMock.mockReturnValue({ user: fakeUser(), status: "signed-in" });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        reply: "Acme is targeting a $40k pilot.",
        meta: { error: null, hits: 5, relevant: 3, top_dist: 0.42 },
      }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    expect(result.current.status).toBe("idle");

    await act(async () => {
      await result.current.ask("What about budget?");
    });

    expect(result.current.status).toBe("success");
    expect(result.current.last?.question).toBe("What about budget?");
    expect(result.current.last?.reply).toBe("Acme is targeting a $40k pilot.");
    expect(result.current.last?.meta.relevant).toBe(3);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://rag.example.com/ask");
    expect((init as RequestInit).method).toBe("POST");
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer fake-id-token",
      "Content-Type": "application/json",
    });
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      question: "What about budget?",
      subject_slug: "acme",
      subject_display: "Acme deal",
    });
  });

  it("passes a refusal reply through unchanged", async () => {
    useAuthMock.mockReturnValue({ user: fakeUser(), status: "signed-in" });
    const refusal = "I don't have anything in folder 'Acme deal' about that.";
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        reply: refusal,
        meta: { error: null, hits: 5, relevant: 0, top_dist: 0.83 },
      }),
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    await act(async () => {
      await result.current.ask("Anything about purple cows?");
    });

    expect(result.current.status).toBe("success");
    expect(result.current.last?.reply).toBe(refusal);
    expect(result.current.last?.meta.relevant).toBe(0);
  });

  it("sets error state when not signed in", async () => {
    useAuthMock.mockReturnValue({ user: null, status: "signed-out" });
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    await act(async () => {
      await result.current.ask("hi");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe("not-signed-in");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sets error state when RAG base URL is not configured", async () => {
    useAuthMock.mockReturnValue({ user: fakeUser(), status: "signed-in" });
    process.env.NEXT_PUBLIC_RAG_BASE_URL = "";
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    await act(async () => {
      await result.current.ask("hi");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe("rag-not-configured");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sets error state on non-2xx HTTP response", async () => {
    useAuthMock.mockReturnValue({ user: fakeUser(), status: "signed-in" });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    await act(async () => {
      await result.current.ask("hi");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe("http-500");
  });

  it("sets error state on network failure", async () => {
    useAuthMock.mockReturnValue({ user: fakeUser(), status: "signed-in" });
    globalThis.fetch = vi.fn().mockRejectedValue(
      new Error("network down"),
    ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    await act(async () => {
      await result.current.ask("hi");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.errorMessage).toBe("network down");
  });

  it("ignores blank questions without changing state", async () => {
    useAuthMock.mockReturnValue({ user: fakeUser(), status: "signed-in" });
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    await act(async () => {
      await result.current.ask("   ");
    });

    expect(result.current.status).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("transitions to loading then success", async () => {
    useAuthMock.mockReturnValue({ user: fakeUser(), status: "signed-in" });
    let resolveFetch: (v: Response) => void = () => {};
    globalThis.fetch = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    ) as unknown as typeof fetch;

    const { result } = renderHook(() => useAsk("acme", "Acme deal"));
    act(() => {
      void result.current.ask("hi");
    });
    await waitFor(() => expect(result.current.status).toBe("loading"));

    await act(async () => {
      resolveFetch({
        ok: true,
        json: async () => ({
          reply: "ok",
          meta: { error: null, hits: 1, relevant: 1, top_dist: 0.1 },
        }),
      } as Response);
    });

    await waitFor(() => expect(result.current.status).toBe("success"));
  });
});
