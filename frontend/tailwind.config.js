/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#09090C",
          surface: "#121216",
          elevated: "#18181F",
        },
        border: {
          DEFAULT: "rgba(255,255,255,0.08)",
          strong: "rgba(255,255,255,0.16)",
        },
        ink: {
          DEFAULT: "#F5F5F7",
          muted: "#9B9BA8",
          faint: "#5C5C68",
        },
        accent: {
          DEFAULT: "#7B61FF",
          soft: "#9B87FF",
          dim: "#4B3FA8",
        },
        coral: {
          DEFAULT: "#FF7A59",
          soft: "#FF9B82",
        },
        success: "#34D399",
        danger: "#FB7185",
      },
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(123, 97, 255, 0.45)",
        "glow-coral": "0 0 40px -10px rgba(255, 122, 89, 0.45)",
        panel: "0 1px 0 0 rgba(255,255,255,0.06) inset",
      },
      backdropBlur: {
        xs: "2px",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        shimmer: "shimmer 2s linear infinite",
      },
    },
  },
  plugins: [],
};
