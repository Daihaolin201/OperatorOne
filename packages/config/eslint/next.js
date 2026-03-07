import { config as baseConfig } from "./index.js";

// Next.js apps extend this config
/** @type {import("eslint").Linter.Config[]} */
export const config = [
  ...baseConfig,
  {
    rules: {
      // Next.js specific rules go here
    },
  },
];
