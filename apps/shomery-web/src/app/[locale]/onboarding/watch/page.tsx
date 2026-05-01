import { setRequestLocale } from "next-intl/server";

import { WatchStep } from "@/components/onboarding/watch-step";

export default async function OnboardingWatchPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <WatchStep />;
}
