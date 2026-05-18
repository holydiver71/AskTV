// Theme registry — server-side only.
// Switch themes via the ASK_TV_THEME environment variable.
//
// To add a new theme:
//   1. Add its ID to THEME_IDS
//   2. Add an entry to `themes` with the HTML classes it needs
//   3. Add a corresponding CSS class block in app/globals.css

export const THEME_IDS = ["default", "radio1"] as const;
export type ThemeId = (typeof THEME_IDS)[number];

interface ThemeConfig {
  // Classes applied to <html>. Include 'dark' for dark themes so that
  // Tailwind's dark: variant and the .dark CSS block both activate.
  htmlClasses: string[];
}

const themes: Record<ThemeId, ThemeConfig> = {
  default: { htmlClasses: ["dark"] },
  // Light theme — no 'dark' class, so dark: Tailwind variants do not apply.
  radio1: { htmlClasses: ["theme-radio1"] },
};

export function getThemeClasses(id: string): string[] {
  const themeId = THEME_IDS.includes(id as ThemeId)
    ? (id as ThemeId)
    : "default";
  return themes[themeId].htmlClasses;
}
