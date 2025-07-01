/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './thinkelearn/templates/**/*.html',
    './home/templates/**/*.html',
    './search/templates/**/*.html',
    './blog/templates/**/*.html',
    './thinkelearn/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors for THINK eLearn - Warm earth tones
        primary: {
          50: '#f7f4f3',
          100: '#ede6e3',
          200: '#d4c4bd',
          300: '#b8a194',
          400: '#9a7e6b',
          500: '#784421', // Secondary brown as primary 500
          600: '#5c3318',
          700: '#432411',
          800: '#361612', // Original primary brown
          900: '#2a110d',
        },
        secondary: {
          50: '#fff4ed',
          100: '#ffe6d1',
          200: '#ffcba3',
          300: '#ffa866',
          400: '#ff8533',
          500: '#ff6600', // Brand orange
          600: '#e55500',
          700: '#cc4400',
          800: '#b33300',
          900: '#992200',
        },
        neutral: {
          50: '#fafaf9',
          100: '#f5f5f4',
          200: '#e7e5e4',
          300: '#d6d3d1',
          400: '#a8a29e',
          500: '#78716c',
          600: '#57534e',
          700: '#44403c',
          800: '#292524',
          900: '#1c1917',
        },
        // Balance colors - Cyan palette based on #B4DFED
        cyan: {
          50: '#f0f9fc',
          100: '#e1f3f8',
          200: '#c3e7f1',
          300: '#b4dfed', // Base color
          400: '#8cc8dd',
          500: '#64b1cd',
          600: '#4a8ba8',
          700: '#376583',
          800: '#24405e',
          900: '#1a2f44',
        },
        // Balance colors - Cream/Yellow palette based on #EEECE1
        cream: {
          50: '#fefefe',
          100: '#fbfaf8',
          200: '#f7f5f0',
          300: '#eeece1', // Base color
          400: '#e2ddc8',
          500: '#d6ceaf',
          600: '#c4b888',
          700: '#a69761',
          800: '#8a7a46',
          900: '#6b5f35',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        heading: ['Poppins', 'system-ui', 'sans-serif'],
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
            color: '#374151',
            a: {
              color: '#ff6600',
              '&:hover': {
                color: '#e55500',
              },
            },
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
  ],
}
