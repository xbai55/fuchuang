/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#111827',
        secondary: '#2563eb',
        dark: '#111827',
        darker: '#0b0f17',
        'dark-lighter': '#111827',
      },
    },
  },
  plugins: [],
}
