/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Exo 2'", "Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI"],
      },
      colors: {
        "bg-base":     "#05080A",
        "bg-elevated": "#070C11",
        "bg-panel":    "#0B1116",
        "bg-muted":    "#131A22",
        "bg-overlay":  "#1E2935",
        "text-primary":   "#F1F5F9",
        "text-secondary": "#CBD5E1",
        "text-muted":     "#64748B",
        "accent-100": "#A5F3FC",
        "accent-200": "#33FDFF",
        "accent-300": "#00F8FA",
        "accent-400": "#00CACC",
        "accent-500": "#009FA1",
        "accent-600": "#007275",
        "accent-700": "#004749",
        "border-soft":   "#1A232C",
        "border-mid":    "#26313C",
        "border-strong": "#334151",
      },
      boxShadow: {
        glow: "0 0 20px rgba(0, 159, 161, 0.25)",
        "glow-sm": "0 0 10px rgba(0, 159, 161, 0.15)",
      },
      borderRadius: {
        "2xl": "20px",
        "3xl": "24px",
      },
    },
  },
  plugins: [],
};
