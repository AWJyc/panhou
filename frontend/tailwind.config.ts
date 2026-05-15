import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // 背景
        page: "#FFFFFF",
        surface: "#FAFAFB",
        raised: "#F4F4F6",
        inverse: "#0A0A0C",
        "accent-soft": "#FFF1EA",
        "rise-soft": "#FCE9EA",
        "fall-soft": "#E3F3E9",

        // 文字
        ink: {
          DEFAULT: "#09090B",
          secondary: "#52525B",
          muted: "#A1A1AA",
          inverse: "#FAFAFA",
        },

        // 边框
        line: {
          subtle: "#EDEDEF",
          DEFAULT: "#D9D9DD",
          strong: "#0A0A0C",
        },

        // 品牌色 (warm orange)
        accent: {
          DEFAULT: "#E84A1C",
          soft: "#FFF1EA",
          deep: "#B53612",
        },

        // A 股惯例：涨红跌绿
        rise: {
          DEFAULT: "#D6242A",
          soft: "#FCE9EA",
          deep: "#A11820",
        },
        fall: {
          DEFAULT: "#0E8A55",
          soft: "#E3F3E9",
          deep: "#08603C",
        },
      },
      fontFamily: {
        sans: [
          '"Geist Variable"',
          '"Noto Sans SC"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "system-ui",
          "sans-serif",
        ],
        mono: [
          '"Geist Mono Variable"',
          "ui-monospace",
          "Menlo",
          "monospace",
        ],
      },
      letterSpacing: {
        tight2: "-0.02em",
        tight3: "-0.04em",
        tight4: "-0.05em",
        wide1: "0.08em",
        wide2: "0.12em",
      },
      maxWidth: {
        content: "1280px",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulse2: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        rise: "rise 0.6s cubic-bezier(0.2, 0.7, 0.2, 1) both",
        livedot: "pulse2 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
