import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "./locales/en/common.json";
import enNavigation from "./locales/en/navigation.json";
import enAuth from "./locales/en/auth.json";
import enErrors from "./locales/en/errors.json";
import zhCommon from "./locales/zh/common.json";
import zhNavigation from "./locales/zh/navigation.json";
import zhAuth from "./locales/zh/auth.json";
import zhErrors from "./locales/zh/errors.json";

export const NAMESPACES = ["common", "navigation", "auth", "errors"] as const;
export type Namespace = (typeof NAMESPACES)[number];

const resources = {
  en: {
    common: enCommon,
    navigation: enNavigation,
    auth: enAuth,
    errors: enErrors,
  },
  zh: {
    common: zhCommon,
    navigation: zhNavigation,
    auth: zhAuth,
    errors: zhErrors,
  },
};

export async function initI18n(locale: "en" | "zh" = "en"): Promise<void> {
  if (i18next.isInitialized) {
    await i18next.changeLanguage(locale);
    return;
  }

  await i18next.use(initReactI18next).init({
    lng: locale,
    fallbackLng: "en",
    defaultNS: "common",
    ns: NAMESPACES,
    resources,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["path", "navigator"],
      lookupFromPathIndex: 0,
    },
  });
}
