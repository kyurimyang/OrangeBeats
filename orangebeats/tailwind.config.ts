import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Pretendard Variable', 'Pretendard', 'Inter', 'system-ui', 'sans-serif'],
        display: ['Pretendard Variable', 'Pretendard', 'Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        orange: {
          DEFAULT: '#FD6D11',
          soft: '#FFB07A',
          deep: '#C24A00',
        },
        mint: {
          DEFAULT: '#5EEAD4',
          soft: '#A6F2E5',
          deep: '#2BB8A3',
        },
        ink: {
          950: '#070707',
          900: '#0a0a0a',
          850: '#101010',
          800: '#161616',
          700: '#1f1f1f',
          600: '#2a2a2a',
          500: '#3a3a3a',
        },
      },
    },
  },
  plugins: [],
};

export default config;
