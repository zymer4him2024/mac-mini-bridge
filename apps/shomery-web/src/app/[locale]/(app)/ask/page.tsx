import { setRequestLocale } from "next-intl/server";

import { AskLandingScreen } from "@/components/ask/ask-landing-screen";

export default async function AskLandingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <AskLandingScreen />;
}
