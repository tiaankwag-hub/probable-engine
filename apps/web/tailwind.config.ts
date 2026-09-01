import type { Config } from "tailwindcss";

/**
 * Severity colors are named semantically (not just "red"/"orange") so
 * risk-band styling stays consistent and greppable across the app —
 * see docs/architecture/01-target-architecture.md on accessible severity
 * colors.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        severity: {
          low: "#1a7f37",
          moderate: "#9a6700",
          high: "#bc4c00",
          extreme: "#cf222e",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f6f8fa",
          border: "#d0d7de",
        },
        accent: {
          DEFAULT: "#4f46e5",
          soft: "#eef2ff",
          hover: "#4338ca",
        },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
