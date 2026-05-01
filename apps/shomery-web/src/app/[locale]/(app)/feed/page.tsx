import { setRequestLocale } from "next-intl/server";

import { FeedScreen } from "@/components/feed/feed-screen";

export default async function FeedPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <FeedScreen />;
}
