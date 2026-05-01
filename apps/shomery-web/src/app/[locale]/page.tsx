import { setRequestLocale } from "next-intl/server";

import { RootRedirect } from "./root-redirect";

export default async function LocaleIndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <RootRedirect />;
}
