import { useTranslations } from "next-intl";

export default function AgentsPage() {
  const t = useTranslations("navigation");
  return (
    <main className="min-h-screen bg-portal-50 p-8">
      <h1 className="text-2xl font-semibold text-portal-900">{t("agents")}</h1>
    </main>
  );
}
