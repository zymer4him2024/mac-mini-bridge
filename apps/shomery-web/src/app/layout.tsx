// Root layout. The localized layout at src/app/[locale]/layout.tsx is what
// actually renders <html> and <body>; this file is required by Next.js but
// delegates everything to children.
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
