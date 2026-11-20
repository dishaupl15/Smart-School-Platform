import { LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label }: LoadingStateProps) {
  const { t } = useTranslation();

  return (
    <div className="loading-state" role="status">
      <LoaderCircle aria-hidden="true" className="loading-spinner" size={20} />
      <span>{label ?? t("common.loading")}</span>
    </div>
  );
}
