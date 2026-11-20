import { useTranslation } from "react-i18next";
import { languageSchema, supportedLanguages } from "@/schemas/language";

export function useLanguage() {
  const { i18n } = useTranslation();
  const currentLanguage = languageSchema.safeParse(
    i18n.resolvedLanguage ?? i18n.language,
  );

  async function changeLanguage(language: string) {
    const result = languageSchema.safeParse(language);
    if (!result.success) {
      throw new Error("Unsupported application language.");
    }

    await i18n.changeLanguage(result.data);
  }

  return {
    language: currentLanguage.success ? currentLanguage.data : "en",
    languages: supportedLanguages,
    changeLanguage,
  };
}
