import { setRequestLocale } from "next-intl/server";

import { SaveStep } from "@/components/onboarding/save-step";

export default async function OnboardingSavePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <SaveStep />;
}
