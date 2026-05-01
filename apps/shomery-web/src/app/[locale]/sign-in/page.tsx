import { setRequestLocale } from "next-intl/server";

import { SignInScreen } from "./sign-in-screen";

export default async function SignInPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <SignInScreen />;
}
