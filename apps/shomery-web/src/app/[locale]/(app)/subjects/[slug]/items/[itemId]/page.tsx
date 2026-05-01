import { setRequestLocale } from "next-intl/server";

import { SubjectItemView } from "@/components/subjects/subject-item-view";

export async function generateStaticParams() {
  const locales = ["en", "ko", "pt-BR"];
  return locales.map((locale) => ({ locale, slug: "_placeholder", itemId: "_placeholder" }));
}

export default async function SubjectItemPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string; itemId: string }>;
}) {
  const { locale, slug, itemId } = await params;
  setRequestLocale(locale);
  return <SubjectItemView slug={slug} itemId={itemId} />;
}
