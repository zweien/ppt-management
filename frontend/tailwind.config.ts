import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // 清华紫 (原型图主色)
        brand: {
          50: "#f3f0ff",
          100: "#e9e2ff",
          200: "#d6c9ff",
          300: "#b8a1ff",
          400: "#9b78f5",
          500: "#6C5CE7",
          600: "#5b4ad0",
          700: "#4a3ba8",
          800: "#3a2d80",
          900: "#2a2059",
        },
      },
    },
  },
  plugins: [],
};
export default config;
