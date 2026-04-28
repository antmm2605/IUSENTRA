import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ius: {
          navy: "#071B33",
          navy2: "#0B2748",
          blue: "#123A63",
          ink: "#0F172A",
          gold: "#C8A24A",
          sky: "#2F80ED",
          surface: "#F6F8FC",
        },
      },
      boxShadow: {
        legal: "0 22px 70px rgba(7, 27, 51, 0.12)",
        panel: "0 14px 34px rgba(15, 23, 42, 0.08)",
      },
      borderRadius: {
        "2xl": "1.25rem",
        "3xl": "1.75rem",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
