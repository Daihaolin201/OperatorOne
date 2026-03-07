import { Button } from "@op1/ui";
import { useTranslations } from "next-intl";

export default function HomePage() {
  const t = useTranslations("product.home");
  const nav = useTranslations("product.nav");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-product-50 p-8">
      <div className="max-w-2xl text-center">
        <h1 className="text-4xl font-bold text-product-900">
          {t("title")}
        </h1>
        <p className="mt-4 text-lg text-product-500">
          {t("subtitle")}
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Button variant="primary" size="lg">
            {t("cta")}
          </Button>
          <Button variant="secondary" size="lg">
            {nav("about")}
          </Button>
        </div>
      </div>
    </main>
  );
}
