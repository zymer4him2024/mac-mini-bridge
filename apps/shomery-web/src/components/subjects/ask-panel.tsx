"use client";

import { useState, type FormEvent } from "react";

import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { useAsk } from "@/lib/use-ask";

const QUESTION_MAX = 2000;

export function AskPanel({
  slug,
  subjectDisplay,
}: {
  slug: string;
  subjectDisplay: string;
}) {
  const t = useTranslations("subjects.ask");
  const { ask, status, last, errorMessage } = useAsk(slug, subjectDisplay);
  const [draft, setDraft] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === "loading") return;
    const trimmed = draft.trim();
    if (!trimmed) return;
    await ask(trimmed);
    setDraft("");
  }

  const errorText = errorMessage ? mapError(errorMessage, t) : null;

  return (
    <section className="flex w-full flex-col">
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <label htmlFor="ask-input" className="sr-only">
          {t("inputPlaceholder")}
        </label>
        <textarea
          id="ask-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={QUESTION_MAX}
          placeholder={t("inputPlaceholder")}
          rows={3}
          disabled={status === "loading"}
          className="w-full resize-y rounded border border-gray-200 bg-paper px-3 py-2 text-sm text-ink placeholder:text-soft focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={status === "loading" || draft.trim().length === 0}
          >
            {status === "loading" ? t("submitPending") : t("submitAction")}
          </Button>
        </div>
      </form>

      {status === "loading" ? (
        <p className="mt-4 text-sm text-soft" aria-busy="true">
          {t("loadingHint")}
        </p>
      ) : null}

      {errorText ? (
        <p className="mt-4 text-sm text-warn" role="alert">
          {errorText}
        </p>
      ) : null}

      {last ? (
        <article className="mt-4 border-l-accent border-brand bg-paper py-4 pl-5 pr-4 shadow-sm">
          <h3 className="text-xs font-bold uppercase tracking-wide text-soft">
            {t("questionHeader")}
          </h3>
          <p className="mt-1 text-sm text-ink">{last.question}</p>

          <h3 className="mt-4 text-xs font-bold uppercase tracking-wide text-soft">
            {t("replyHeader")}
          </h3>
          <div className="mt-1 text-sm text-ink">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => (
                  <p className="my-2 text-sm leading-6 text-ink">{children}</p>
                ),
                ul: ({ children }) => (
                  <ul className="my-2 list-disc space-y-1 pl-5 text-sm text-ink">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="my-2 list-decimal space-y-1 pl-5 text-sm text-ink">
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
              }}
            >
              {last.reply}
            </ReactMarkdown>
          </div>

          <p className="mt-3 text-xs text-soft">
            {t("metaLabel", {
              hits: last.meta.hits,
              relevant: last.meta.relevant,
            })}
          </p>
        </article>
      ) : null}
    </section>
  );
}

function mapError(
  code: string,
  t: ReturnType<typeof useTranslations<"subjects.ask">>,
): string {
  if (code === "rag-not-configured") return t("errorNotConfigured");
  if (code === "not-signed-in") return t("errorNotSignedIn");
  return t("errorGeneric");
}
