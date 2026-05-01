import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// STATIC_EXPORT=1 builds the static-export bundle for Firebase Hosting
// (`pnpm build:static` → `out/`). Plain `pnpm build` keeps Next.js in SSR
// mode so `next start` and Playwright's webServer keep working.
const staticExport = process.env.STATIC_EXPORT === "1";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  ...(staticExport && {
    output: "export",
    images: { unoptimized: true },
    trailingSlash: true,
  }),
};

export default withNextIntl(nextConfig);
