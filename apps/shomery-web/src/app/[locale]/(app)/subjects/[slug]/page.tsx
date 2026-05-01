import { setRequestLocale } from "next-intl/server";

import { SubjectDetail } from "@/components/subjects/subject-detail";

export default async function SubjectPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  return <SubjectDetail slug={slug} />;
}
