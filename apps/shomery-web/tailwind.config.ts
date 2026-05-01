import type { Config } from "tailwindcss";

/**
 * Brand tokens are the source of truth for color in Shomery.
 * See apps/shomery-web/CLAUDE.md § "Brand guardrails".
 *
 * Light mode only in v1. Do not introduce a `dark:` prefix.
 */
const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#10B981",
          hover: "#059669",
          tint: "#ECFDF5",
        },
        ink: "#111111",
        soft: "#6B7280",
        paper: "#FFFFFF",
        warn: "#F59E0B",
        channel: {
          kakao: "#FEE500",
          whatsapp: "#25D366",
          telegram: "#0088CC",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      fontWeight: {
        normal: "400",
        bold: "700",
      },
      borderWidth: {
        accent: "3px",
      },
    },
  },
  plugins: [],
};

export default config;
