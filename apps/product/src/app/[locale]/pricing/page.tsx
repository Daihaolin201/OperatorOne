import { useTranslations } from "next-intl";
import { Card, CardTitle } from "@op1/ui";

export default function PricingPage() {
  const t = useTranslations("common");

  return (
    <main className="min-h-screen bg-product-50 p-8">
      <div className="mx-auto max-w-4xl text-center">
        <h1 className="text-3xl font-bold text-product-900">Pricing</h1>
        <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
          {["Starter", "Pro", "Enterprise"].map((plan) => (
            <Card key={plan} className="text-left">
              <CardTitle>{plan}</CardTitle>
            </Card>
          ))}
        </div>
      </div>
    </main>
  );
}
