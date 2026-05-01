import { setRequestLocale } from "next-intl/server";

import { WelcomeScreen } from "@/components/onboarding/welcome-screen";

export default async function OnboardingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <WelcomeScreen />;
}
