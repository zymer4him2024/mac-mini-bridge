import { setRequestLocale } from "next-intl/server";

import { SubjectDetail } from "@/components/subjects/subject-detail";

export async function generateStaticParams() {
  const locales = ["en", "ko", "pt-BR"];
  return locales.map((locale) => ({ locale, slug: "_placeholder" }));
}

export default async function SubjectPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  return <SubjectDetail slug={slug} />;
}
