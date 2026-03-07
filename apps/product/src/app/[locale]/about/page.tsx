import { useTranslations } from "next-intl";

export default function AboutPage() {
  const t = useTranslations("product.about");

  return (
    <main className="min-h-screen bg-product-50 p-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-3xl font-bold text-product-900">{t("title")}</h1>
        <p className="mt-4 text-product-500">
          {t("content")}
        </p>
      </div>
    </main>
  );
}
