/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media", // follow system preference
  theme: {
    extend: {
      colors: {
        // Slate-based neutral palette
        bg: {
          DEFAULT: "rgb(248 250 252)",
          dark: "rgb(15 23 42)",
        },
        surface: {
          DEFAULT: "rgb(255 255 255)",
          dark: "rgb(30 41 59)",
        },
      },
    },
  },
  plugins: [],
};
