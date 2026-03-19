/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./popup/**/*.html", "./popup/**/*.js"],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'sans-serif'] },
      colors: {
        bg:       '#111110',
        surface:  '#1c1c1a',
        surface2: '#242422',
        border:   '#2e2e2b',
        border2:  '#3a3a36',
        accent:   '#a8a29e',
        text:     '#e7e5e4',
        'text-dim':   '#a8a29e',
        muted:        '#78716c',
      }
    }
  },
  plugins: [],
}
