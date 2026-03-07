import { Card, CardTitle } from "@op1/ui";
import { useTranslations } from "next-intl";

export default function PricingPage() {
  const t = useTranslations("product.pricing");

  const plans: Array<"free" | "pro" | "enterprise"> = ["free", "pro", "enterprise"];

  return (
    <main className="min-h-screen bg-product-50 p-8">
      <div className="mx-auto max-w-4xl text-center">
        <h1 className="text-3xl font-bold text-product-900">{t("title")}</h1>
        <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
          {plans.map((plan) => (
            <Card key={plan} className="text-left">
              <CardTitle>{t(`${plan}.title`)}</CardTitle>
            </Card>
          ))}
        </div>
      </div>
    </main>
  );
}
