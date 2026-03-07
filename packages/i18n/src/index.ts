/**
 * @op1/i18n — public API
 *
 * Usage in apps:
 *   import { initI18n, useTranslation, SUPPORTED_LOCALES } from '@op1/i18n'
 */

// Runtime init + config
export { initI18n } from "./config.js";

// Re-export useTranslation so apps only need @op1/i18n as a dependency
export { useTranslation } from "react-i18next";

// Supported locale list (canonical)
export const SUPPORTED_LOCALES = ["en", "zh"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

// Type exports
export * from "./types.js";
