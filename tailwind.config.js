module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  daisyui: {
    themes: [
      {
        light: {
          ...require("daisyui/src/theming/themes")["winter"],
          primary: "#1961dd",
          warning: "#fde68a",
          success: "#bbf7d0",
          error: "#ef4444"
        },
      },
    ],
  },

  theme: {
    extend: {},
  },
  plugins: [
    require("@tailwindcss/typography"),
    require('daisyui')
  ],
};
