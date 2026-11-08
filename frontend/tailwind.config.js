/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          canvas: "var(--surface-canvas)",
          elevated: "var(--surface-elevated)",
          subtle: "var(--surface-subtle)",
          hairline: "var(--border-hairline)",
          strong: "var(--border-strong)",
        },
        content: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        action: {
          primary: "var(--action-primary)",
          hover: "var(--action-primary-hover)",
          focus: "var(--action-focus-ring)",
          danger: "var(--action-danger)",
        },
        semantic: {
          winnerBg: "var(--winner-bg)",
          winnerText: "var(--winner-text)",
          hitlBg: "var(--hitl-warning-bg)",
          hitlBorder: "var(--hitl-warning-border)",
          hitlText: "var(--hitl-warning-text)",
          notCarriedBg: "var(--not-carried-bg)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        control: "4px",
        container: "6px",
      },
    },
  },
  plugins: [],
}
