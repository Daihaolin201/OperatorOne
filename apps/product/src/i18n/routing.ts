import { defineRouting } from "next-intl/routing";
import { locales, defaultLocale } from "@op1/i18n/types";

export const routing = defineRouting({
  locales,
  defaultLocale,
  localePrefix: "as-needed",
});
