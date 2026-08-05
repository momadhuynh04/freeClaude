/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        moss: {
          50: '#e8f5e4',
          100: '#c8e6c1',
          200: '#a5d69b',
          300: '#81c674',
          400: '#66b957',
          500: '#4a7c4f',
          600: '#3d6b42',
          700: '#2f5a35',
          800: '#224a29',
          900: '#1a2e1a',
          950: '#0f1a0f',
        },
        claude: {
          400: '#ffb347',
          500: '#ff8c42',
          600: '#e67e22',
          700: '#cc6b1a',
        },
        provider: {
          400: '#5dade2',
          500: '#3498db',
          600: '#2980b9',
          700: '#1f6fa8',
        },
      },
      fontFamily: {
        pixel: ['"Press Start 2P"', 'monospace'],
      },
      borderRadius: {
        none: '0',
        sm: '0.125rem',
        md: '0',
        lg: '0',
        xl: '0',
        '2xl': '0',
        '3xl': '0',
      },
    },
  },
  plugins: [],
}
