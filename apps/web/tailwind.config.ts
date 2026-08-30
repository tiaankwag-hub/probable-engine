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
      },
    },
  },
  plugins: [],
};

export default config;
