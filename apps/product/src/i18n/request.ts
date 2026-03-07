import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;

  if (!locale || !routing.locales.includes(locale as "en" | "zh")) {
    locale = routing.defaultLocale;
  }

  const [common, navigation, auth, errors] = await Promise.all([
    import(`@op1/i18n/locales/${locale}/common.json`),
    import(`@op1/i18n/locales/${locale}/navigation.json`),
    import(`@op1/i18n/locales/${locale}/auth.json`),
    import(`@op1/i18n/locales/${locale}/errors.json`),
  ]);

  return {
    locale,
    messages: {
      common: common.default,
      navigation: navigation.default,
      auth: auth.default,
      errors: errors.default,
    },
  };
});
