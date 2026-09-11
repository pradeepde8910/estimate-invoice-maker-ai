import typography from '@tailwindcss/typography'

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Google Sans Flex"',
          '"Google Sans"',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
      },
      colors: {
        brand: {
          50: '#f0fdf6',
          100: '#dcfce9',
          200: '#bbf7d4',
          300: '#86efb3',
          400: '#4ade8c',
          500: '#22c569',
          600: '#16a34f',
          700: '#0f7d3d',
          800: '#0d6331',
          900: '#0b5129',
        },
        pixous: {
          blue: '#184C96',
          teal: '#18C7A1',
          dark: '#0e2a47',
        },
        coral: {
          50: '#fff3f4',
          100: '#ffe1e4',
          200: '#ffc7cf',
          300: '#ffa0ae',
          400: '#ff7086',
          500: '#fb4a68',
          600: '#e12f52',
          700: '#bd2143',
        },
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgba(11, 40, 25, 0.04), 0 8px 24px -8px rgba(11, 40, 25, 0.08)',
      },
      keyframes: {
        'download-drop': {
          '0%': { transform: 'translateY(-40%)', opacity: '0' },
          '30%': { transform: 'translateY(0)', opacity: '1' },
          '60%': { transform: 'translateY(0)', opacity: '1' },
          '100%': { transform: 'translateY(40%)', opacity: '0' },
        },
        'shimmer': {
          '100%': { transform: 'translateX(100%)' }
        },
        'pop-in': {
          '0%': { transform: 'scale(0.4)', opacity: '0' },
          '60%': { transform: 'scale(1.15)', opacity: '1' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      animation: {
        'download-drop': 'download-drop 1s ease-in-out infinite',
        'pop-in': 'pop-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
    },
  },
  plugins: [typography],
}
