import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "@/i18n/locales/en/common.json";
import hi from "@/i18n/locales/hi/common.json";
import mr from "@/i18n/locales/mr/common.json";

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    mr: { translation: mr },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
