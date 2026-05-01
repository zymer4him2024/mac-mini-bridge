import { setRequestLocale } from "next-intl/server";

import { ConnectStep } from "@/components/onboarding/connect-step";

export default async function OnboardingConnectPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ConnectStep />;
}
