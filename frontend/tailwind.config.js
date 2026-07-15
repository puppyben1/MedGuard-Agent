/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        risk: {
          low: "#16a34a",
          moderate: "#f59e0b",
          high: "#f97316",
          critical: "#dc2626",
          unknown: "#6b7280",
        },
      },
    },
  },
  plugins: [],
};
