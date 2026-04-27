import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./stores/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        parchment: "#f4efe5",
        ink: "#162033",
        accent: "#0f766e",
        bronze: "#b7791f",
        line: "#d8d0c2",
        mist: "#eef3f1",
        danger: "#b42318",
        warning: "#b54708",
        success: "#027a48",
      },
      boxShadow: {
        panel: "0 18px 50px rgba(18, 29, 46, 0.08)",
        focus: "0 0 0 3px rgba(15, 118, 110, 0.18)",
      },
      borderRadius: {
        panel: "24px",
      },
      backgroundImage: {
        "paper-grid": "linear-gradient(rgba(22, 32, 51, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(22, 32, 51, 0.03) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "22px 22px",
      },
    },
  },
  plugins: [],
};

export default config;