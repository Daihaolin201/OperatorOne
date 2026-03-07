import { useTranslations } from "next-intl";
import { Link } from "@/components/link";

export default function HomePage() {
  const t = useTranslations("common");
  const nav = useTranslations("navigation");

  return (
    <main className="min-h-screen bg-portal-50 p-8">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-3xl font-bold text-portal-900">
          {t("appName")} — Portal
        </h1>
        <p className="mt-2 text-portal-500">Internal operations platform</p>
        <nav className="mt-8 flex gap-4">
          <Link href="/dashboard">{nav("dashboard")}</Link>
          <Link href="/agents">{nav("agents")}</Link>
          <Link href="/ventures">{nav("ventures")}</Link>
        </nav>
      </div>
    </main>
  );
}
