import { useTranslations } from "next-intl";
import { Button } from "@op1/ui";

export default function HomePage() {
  const t = useTranslations("common");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-product-50 p-8">
      <div className="max-w-2xl text-center">
        <h1 className="text-4xl font-bold text-product-900">
          {t("appName")}
        </h1>
        <p className="mt-4 text-lg text-product-500">
          AI-powered startup execution — from idea to revenue.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Button variant="primary" size="lg">
            Get Started
          </Button>
          <Button variant="secondary" size="lg">
            Learn More
          </Button>
        </div>
      </div>
    </main>
  );
}
