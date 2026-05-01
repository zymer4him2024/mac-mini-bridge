import { setRequestLocale } from "next-intl/server";

import { SettingsScreen } from "@/components/settings/settings-screen";

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <SettingsScreen />;
}
