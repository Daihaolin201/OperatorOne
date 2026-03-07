/**
 * Type-safe i18n resource interface.
 * Derived from the English locale files (canonical source of truth).
 * Apps import this to get type-checked translation keys.
 */

import type common from "./locales/en/common.json";
import type navigation from "./locales/en/navigation.json";
import type auth from "./locales/en/auth.json";
import type errors from "./locales/en/errors.json";

export interface I18nResources {
  common: typeof common;
  navigation: typeof navigation;
  auth: typeof auth;
  errors: typeof errors;
}

export type Locale = "en" | "zh";

export const locales: Locale[] = ["en", "zh"];
export const defaultLocale: Locale = "en";

export const localeLabels: Record<Locale, string> = {
  en: "English",
  zh: "中文",
};
