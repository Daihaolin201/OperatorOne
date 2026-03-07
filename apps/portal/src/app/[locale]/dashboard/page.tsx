import { useTranslations } from "next-intl";
import { Card, CardTitle } from "@op1/ui";

export default function DashboardPage() {
  const t = useTranslations("navigation");

  return (
    <main className="min-h-screen bg-portal-50 p-8">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-semibold text-portal-900">{t("dashboard")}</h1>
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardTitle>Agent Status</CardTitle>
          </Card>
          <Card>
            <CardTitle>Pipeline Overview</CardTitle>
          </Card>
          <Card>
            <CardTitle>KPIs</CardTitle>
          </Card>
        </div>
      </div>
    </main>
  );
}
