import { setRequestLocale } from "next-intl/server";

import { SubjectAskView } from "@/components/subjects/subject-ask-view";

export async function generateStaticParams() {
  const locales = ["en", "ko", "pt-BR"];
  return locales.map((locale) => ({ locale, slug: "_placeholder" }));
}

export default async function SubjectAskPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  return <SubjectAskView slug={slug} />;
}
