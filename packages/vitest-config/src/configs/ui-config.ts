import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * Vitest config for React component packages (uses jsdom + @testing-library)
 */
export const uiConfig = defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "istanbul",
      reporter: [
        "text",
        "lcov",
        ["json", { file: "../coverage.json" }],
      ],
      enabled: true,
      include: ["src/**/*.tsx", "src/**/*.ts"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/**/*.spec.{ts,tsx}",
        "src/index.ts",
      ],
    },
  },
});
