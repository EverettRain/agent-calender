import { useEffect } from "react";
import { usePreferences } from "@/store/preferences";

/**
 * Sync the document root's "dark" class with the user's theme preference.
 * - "auto"  → follow prefers-color-scheme: dark
 * - "light" → no class
 * - "dark"  → always class="dark"
 */
export function useTheme(): void {
  const theme = usePreferences((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");

    const apply = () => {
      const shouldDark =
        theme === "dark" || (theme === "auto" && mql.matches);
      root.classList.toggle("dark", shouldDark);
    };

    apply();
    if (theme === "auto") {
      mql.addEventListener("change", apply);
      return () => mql.removeEventListener("change", apply);
    }
  }, [theme]);
}
