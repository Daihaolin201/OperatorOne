import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

const localeLoaders = {
  en: {
    common: () => import("@op1/i18n/locales/en/common.json"),
    navigation: () => import("@op1/i18n/locales/en/navigation.json"),
    auth: () => import("@op1/i18n/locales/en/auth.json"),
    errors: () => import("@op1/i18n/locales/en/errors.json"),
    portal: () => import("@op1/i18n/locales/en/portal.json"),
  },
  zh: {
    common: () => import("@op1/i18n/locales/zh/common.json"),
    navigation: () => import("@op1/i18n/locales/zh/navigation.json"),
    auth: () => import("@op1/i18n/locales/zh/auth.json"),
    errors: () => import("@op1/i18n/locales/zh/errors.json"),
    portal: () => import("@op1/i18n/locales/zh/portal.json"),
  },
} as const;

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;

  if (!locale || !routing.locales.includes(locale as "en" | "zh")) {
    locale = routing.defaultLocale;
  }

  const loaders = localeLoaders[locale as "en" | "zh"];

  const [common, navigation, auth, errors, portal] = await Promise.all([
    loaders.common(),
    loaders.navigation(),
    loaders.auth(),
    loaders.errors(),
    loaders.portal(),
  ]);

  return {
    locale,
    messages: {
      common: common.default,
      navigation: navigation.default,
      auth: auth.default,
      errors: errors.default,
      portal: portal.default,
    },
  };
});
