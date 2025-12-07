module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],

  theme: {
    extend: {
      colors: {
        'neon-violet': '#FF5F1F', // Neon Orange
        'neon-purple': '#EA580C', // Deep Orange
        'deep-bg': '#050505',
        'card-bg': '#0f0f0f',
        'glass-border': 'rgba(255, 255, 255, 0.08)',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      borderRadius: {
        '4xl': '2rem',
        '5xl': '3rem', 
        'pill': '9999px',
      },
      backdropBlur: {
        'xs': '2px',
      }
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
  ],
};
