/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#6366f1',
        secondary: '#8b5cf6',
        dark: '#1a1a2e',
        darker: '#16162a',
        'dark-lighter': '#1e1e38',
      },
    },
  },
  plugins: [],
}
