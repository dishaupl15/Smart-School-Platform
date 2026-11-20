import { z } from "zod";

export const languageSchema = z.enum(["en", "hi", "mr"]);
export type LanguageCode = z.infer<typeof languageSchema>;

export const supportedLanguages: ReadonlyArray<{
  code: LanguageCode;
  label: string;
}> = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी" },
  { code: "mr", label: "मराठी" },
];
