import { ArrowUpRight, BookOpenCheck, CircleHelp, Layers3 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";

export function WelcomePage() {
  const { t } = useTranslation();

  return (
    <div className="welcome-page">
      <section className="welcome-heading">
        <div className="eyebrow">{t("dashboard.eyebrow")}</div>
        <h1>{t("dashboard.title")}</h1>
        <p>{t("dashboard.description")}</p>
      </section>

      <section className="foundation-card" aria-labelledby="foundation-title">
        <div className="foundation-icon">
          <BookOpenCheck aria-hidden="true" size={24} />
        </div>
        <div className="foundation-copy">
          <div className="eyebrow">{t("dashboard.foundationEyebrow")}</div>
          <h2 id="foundation-title">{t("dashboard.foundationTitle")}</h2>
          <p>{t("dashboard.foundationDescription")}</p>
        </div>
        <Button
          variant="outline"
          className="foundation-action"
          onClick={() =>
            document
              .getElementById("next-steps")
              ?.scrollIntoView?.({ behavior: "smooth" })
          }
        >
          {t("dashboard.exploreFoundation")}
          <ArrowUpRight aria-hidden="true" size={16} />
        </Button>
      </section>

      <section className="section-block" id="next-steps">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("dashboard.sectionEyebrow")}</div>
            <h2>{t("dashboard.sectionTitle")}</h2>
          </div>
          <span className="phase-pill">{t("dashboard.phaseLabel")}</span>
        </div>
        <div className="next-step-grid">
          <article className="step-card">
            <div className="step-icon blue">
              <Layers3 aria-hidden="true" size={20} />
            </div>
            <span className="step-index">{t("dashboard.stepOne")}</span>
            <h3>{t("dashboard.stepOneTitle")}</h3>
            <p>{t("dashboard.stepOneDescription")}</p>
          </article>
          <article className="step-card">
            <div className="step-icon violet">
              <CircleHelp aria-hidden="true" size={20} />
            </div>
            <span className="step-index">{t("dashboard.stepTwo")}</span>
            <h3>{t("dashboard.stepTwoTitle")}</h3>
            <p>{t("dashboard.stepTwoDescription")}</p>
          </article>
        </div>
      </section>

      <footer className="shell-note">{t("dashboard.noDataNote")}</footer>
    </div>
  );
}
