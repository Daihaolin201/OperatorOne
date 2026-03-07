"use client";

import { useTranslations, useLocale } from "next-intl";
import { createNavigation } from "next-intl/navigation";
import { routing } from "@/i18n/routing";

const { Link, usePathname } = createNavigation(routing);

export default function Nav() {
  const t = useTranslations("product.nav");
  const locale = useLocale();
  const pathname = usePathname();

  return (
    <nav className="flex items-center justify-between p-4 bg-gray-100 border-b">
      <div className="flex gap-4">
        <Link href="/" className="hover:underline">
          {t("home")}
        </Link>
        <Link href="/about" className="hover:underline">
          {t("about")}
        </Link>
        <Link href="/pricing" className="hover:underline">
          {t("pricing")}
        </Link>
      </div>
      <div className="flex gap-2">
        <Link
          href={pathname}
          locale="en"
          className={`px-2 py-1 rounded ${
            locale === "en" ? "bg-blue-500 text-white" : "bg-white text-black"
          }`}
        >
          EN
        </Link>
        <Link
          href={pathname}
          locale="zh"
          className={`px-2 py-1 rounded ${
            locale === "zh" ? "bg-red-500 text-white" : "bg-white text-black"
          }`}
        >
          中文
        </Link>
      </div>
    </nav>
  );
}
