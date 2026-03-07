import type { Config } from "tailwindcss";

// Shared Tailwind base config for all apps
const config: Omit<Config, "content"> = {
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          900: "#1e3a8a",
        },
        // Portal (internal) accent — slate
        portal: {
          50: "#f8fafc",
          500: "#64748b",
          900: "#0f172a",
        },
        // Product (external) accent — indigo
        product: {
          50: "#eef2ff",
          500: "#6366f1",
          900: "#312e81",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
