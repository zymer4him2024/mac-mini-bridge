"use client";

import type { ReactNode } from "react";

import { useTranslations } from "next-intl";

const TOTAL_STEPS = 3;

export function OnboardingShell({
  step,
  children,
}: {
  step: 1 | 2 | 3 | "welcome";
  children: ReactNode;
}) {
  const t = useTranslations("onboarding");
  const isStep = step !== "welcome";

  return (
    <main className="flex min-h-screen flex-col bg-paper text-ink">
      <div className="border-l-accent border-brand mx-auto w-full max-w-md flex-1 px-6 py-10 sm:py-16">
        {isStep ? (
          <div className="mb-8 flex items-center gap-3">
            <div
              role="progressbar"
              aria-valuemin={1}
              aria-valuemax={TOTAL_STEPS}
              aria-valuenow={step}
              aria-label={t("stepLabel", {
                current: step,
                total: TOTAL_STEPS,
              })}
              className="flex items-center gap-1.5"
            >
              {Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1).map(
                (n) => (
                  <span
                    key={n}
                    className={`h-2 w-2 rounded-full ${
                      n === step
                        ? "bg-brand"
                        : n < step
                          ? "bg-brand/60"
                          : "bg-soft/30"
                    }`}
                  />
                ),
              )}
            </div>
            <span className="text-xs text-soft">
              {t("stepLabel", { current: step, total: TOTAL_STEPS })}
            </span>
          </div>
        ) : null}

        {children}
      </div>
    </main>
  );
}
