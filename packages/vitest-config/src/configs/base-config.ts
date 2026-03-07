import { defineConfig } from "vitest/config";

/**
 * Base Vitest config for non-UI packages (pure TS logic, utilities, etc.)
 */
export const baseConfig = defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "istanbul",
      reporter: [
        "text",
        "lcov",
        ["json", { file: "../coverage.json" }],
      ],
      enabled: true,
      include: ["src/**/*.ts"],
      exclude: ["src/**/*.test.ts", "src/**/*.spec.ts", "src/index.ts"],
    },
  },
});
