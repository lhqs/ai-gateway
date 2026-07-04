/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        panel: "#f7f8f8",
        line: "#d9dedc",
        accent: "#0f766e"
      }
    }
  },
  plugins: []
};
