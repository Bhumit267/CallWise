import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./contexts/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        border: "var(--border)",
        brutal: {
          bg: "#fcfbf7",
          canvas: "#f4f3ef",
          black: "#0a0a0a",
          white: "#ffffff",
          yellow: "#ffe600",
          "yellow-light": "#fef9c3",
          blue: "#2563eb",
          "blue-light": "#dbeafe",
          coral: "#ff5a5a",
          "coral-light": "#fee2e2",
          mint: "#10b981",
          "mint-light": "#dcfce7",
          purple: "#a855f7",
          "purple-light": "#f3e8ff",
          cyan: "#06b6d4",
          "cyan-light": "#cffafe",
        },
        primary: {
          DEFAULT: "#2563eb",
          foreground: "#ffffff",
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
      },
      boxShadow: {
        'brutal-xs': '1.5px 1.5px 0px 0px #000000',
        'brutal-sm': '3px 3px 0px 0px #000000',
        'brutal': '5px 5px 0px 0px #000000',
        'brutal-lg': '7px 7px 0px 0px #000000',
        'brutal-xl': '10px 10px 0px 0px #000000',
        'brutal-yellow': '5px 5px 0px 0px #ffe600',
        'brutal-blue': '5px 5px 0px 0px #2563eb',
        'brutal-coral': '5px 5px 0px 0px #ff5a5a',
      },
      borderWidth: {
        '3': '3px',
      },
    },
  },
  plugins: [],
};
export default config;
