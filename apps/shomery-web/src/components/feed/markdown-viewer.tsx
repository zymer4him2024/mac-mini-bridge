"use client";

import { useEffect, useState } from "react";

import type { FolderItem } from "@shomery/shared-types";
import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  MarkdownDriveNotReadyError,
  MarkdownNotEmittedError,
  getMarkdown,
} from "@/lib/markdown";

type ViewerState =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "drive-not-ready" }
  | { kind: "error" }
  | { kind: "ready"; content: string };

export function MarkdownViewer({ item }: { item: FolderItem }) {
  const t = useTranslations("markdown");
  const [state, setState] = useState<ViewerState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    getMarkdown(item)
      .then((content) => {
        if (!cancelled) setState({ kind: "ready", content });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof MarkdownNotEmittedError) {
          setState({ kind: "empty" });
        } else if (err instanceof MarkdownDriveNotReadyError) {
          setState({ kind: "drive-not-ready" });
        } else {
          setState({ kind: "error" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [item]);

  if (state.kind === "loading") {
    return (
      <p className="text-sm text-soft" aria-busy="true">
        {t("loading")}
      </p>
    );
  }

  if (state.kind === "empty") {
    return <p className="text-sm text-soft">{t("empty")}</p>;
  }

  if (state.kind === "drive-not-ready") {
    return <p className="text-sm text-soft">{t("driveNotReady")}</p>;
  }

  if (state.kind === "error") {
    return (
      <p className="text-sm text-warn" role="alert">
        {t("error")}
      </p>
    );
  }

  return (
    <div className="text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-3 mt-6 text-xl font-bold text-ink">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-5 text-lg font-bold text-ink">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-4 text-base font-bold text-ink">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="my-3 text-sm leading-6 text-ink">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="my-3 list-disc space-y-1 pl-6 text-sm text-ink">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="my-3 list-decimal space-y-1 pl-6 text-sm text-ink">
              {children}
            </ol>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand hover:text-brand-hover underline"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-soft/10 px-1 py-0.5 font-mono text-xs text-ink">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-3 overflow-x-auto rounded bg-soft/10 p-3 font-mono text-xs text-ink">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-2 border-brand bg-brand-tint py-2 pl-3 text-sm text-ink">
              {children}
            </blockquote>
          ),
        }}
      >
        {state.content}
      </ReactMarkdown>
    </div>
  );
}
