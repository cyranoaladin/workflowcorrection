import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / .04), 0 1px 2px -1px rgb(0 0 0 / .03)",
        "card-hover": "0 10px 25px -5px rgb(0 0 0 / .08), 0 4px 10px -3px rgb(0 0 0 / .04)",
        "glow": "0 0 20px -5px rgb(99 102 241 / .25)",
        "glow-sm": "0 0 10px -3px rgb(99 102 241 / .2)",
        "inner-glow": "inset 0 1px 1px rgb(255 255 255 / .8)",
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "0.9rem" }],
      },
      animation: {
        "fade-in": "fadeIn .3s ease-out",
        "slide-up": "slideUp .3s ease-out",
        "slide-down": "slideDown .2s ease-out",
        "scale-in": "scaleIn .2s ease-out",
        "spin-slow": "spin 3s linear infinite",
        "number-up": "numberUp .6s ease-out",
      },
      keyframes: {
        fadeIn: { from: { opacity: "0" }, to: { opacity: "1" } },
        slideUp: { from: { opacity: "0", transform: "translateY(10px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        slideDown: { from: { opacity: "0", transform: "translateY(-10px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        scaleIn: { from: { opacity: "0", transform: "scale(0.95)" }, to: { opacity: "1", transform: "scale(1)" } },
        numberUp: { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
    },
  },
  plugins: [],
} satisfies Config;

