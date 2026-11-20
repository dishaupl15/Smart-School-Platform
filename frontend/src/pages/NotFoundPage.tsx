import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <main className="error-screen">
      <div className="eyebrow">404</div>
      <h1>{t("errors.notFoundTitle")}</h1>
      <p>{t("errors.notFoundBody")}</p>
      <Link className="text-link" to="/">
        {t("errors.returnHome")}
      </Link>
    </main>
  );
}
