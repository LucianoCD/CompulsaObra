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
          focus: "var(--action-focus)",
          danger: "var(--action-danger)",
        },
        brand: {
          markBg: "var(--brand-mark-bg)",
          markFg: "var(--brand-mark-fg)",
          markAccent: "var(--brand-mark-accent)",
        },
        semantic: {
          winnerBg: "var(--winner-bg)",
          winnerText: "var(--winner-text)",
          hitlBg: "var(--hitl-bg)",
          hitlBorder: "var(--hitl-border)",
          hitlText: "var(--hitl-text)",
          dangerBg: "var(--danger-bg)",
          dangerBorder: "var(--danger-border)",
          dangerText: "var(--danger-text)",
          infoBg: "var(--info-bg)",
          infoText: "var(--info-text)",
          notCarriedBg: "var(--not-carried-bg)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        control: "8px",
        container: "12px",
        pill: "9999px",
      },
      boxShadow: {
        card: "0 2px 8px -2px rgba(28, 25, 23, 0.06)",
        modal: "0 20px 25px -5px rgba(28, 25, 23, 0.18)",
      },
    },
  },
  plugins: [],
}
