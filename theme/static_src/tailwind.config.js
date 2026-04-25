/**
 * Tailwind theme inspired by parking.brussels :
 * - Bleu profond royal (primary)
 * - Cyan lumineux (accent)
 * - Jaune signalisation (highlight)
 * - Police Inter pour un look moderne et clair
 * - Animations subtiles (fade, slide, scale)
 */
module.exports = {
    content: [
        '../templates/**/*.html',
        '../../templates/**/*.html',
        '../../**/templates/**/*.html',
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
                display: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            colors: {
                // Bleu marque (parking.brussels) — du clair au profond
                brand: {
                    50:  '#EDF5FC',
                    100: '#D4E7F8',
                    200: '#A8CFF1',
                    300: '#75B0E5',
                    400: '#4A92D6',
                    500: '#2375C0',   // primary
                    600: '#0F5BA3',
                    700: '#08447F',
                    800: '#063562',
                    900: '#042648',
                    950: '#021730',
                },
                // Cyan d'accentuation (signalisation moderne)
                accent: {
                    50:  '#ECFDFF',
                    100: '#CFF9FE',
                    200: '#A5F0FC',
                    300: '#67E3F9',
                    400: '#22CDEE',
                    500: '#06B0D4',   // accent
                    600: '#0891B2',
                    700: '#0E7490',
                    800: '#155E75',
                    900: '#164E63',
                },
                // Jaune signalisation parking
                signal: {
                    50:  '#FFFDEA',
                    100: '#FFF7C2',
                    200: '#FFEC85',
                    300: '#FFDC3D',
                    400: '#FFCD00',   // primary signal
                    500: '#E6B400',
                    600: '#B38C00',
                    700: '#806300',
                },
            },
            boxShadow: {
                'brand': '0 10px 30px -10px rgba(8, 68, 127, 0.35)',
                'brand-lg': '0 25px 50px -12px rgba(8, 68, 127, 0.45)',
                'soft': '0 2px 12px -3px rgba(15, 23, 42, 0.08)',
                'card': '0 1px 3px rgba(0,0,0,0.04), 0 4px 16px -2px rgba(0,0,0,0.06)',
            },
            backgroundImage: {
                'brand-gradient':       'linear-gradient(135deg, #08447F 0%, #2375C0 60%, #06B0D4 100%)',
                'brand-gradient-soft':  'linear-gradient(135deg, #EDF5FC 0%, #FFFFFF 60%, #ECFDFF 100%)',
                'hero-pattern':         'radial-gradient(circle at 20% 20%, rgba(35, 117, 192, 0.12) 0%, transparent 50%), radial-gradient(circle at 80% 60%, rgba(6, 176, 212, 0.10) 0%, transparent 50%)',
            },
            animation: {
                'fade-in':       'fadeIn 0.5s ease-out',
                'fade-in-up':    'fadeInUp 0.6s ease-out both',
                'fade-in-down':  'fadeInDown 0.6s ease-out both',
                'slide-in-right':'slideInRight 0.5s ease-out both',
                'scale-in':      'scaleIn 0.4s ease-out both',
                'float':         'float 6s ease-in-out infinite',
                'pulse-slow':    'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'shimmer':       'shimmer 2.5s linear infinite',
            },
            keyframes: {
                fadeIn:        { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
                fadeInUp:      { '0%': { opacity: 0, transform: 'translateY(20px)' },
                                 '100%': { opacity: 1, transform: 'translateY(0)' } },
                fadeInDown:    { '0%': { opacity: 0, transform: 'translateY(-15px)' },
                                 '100%': { opacity: 1, transform: 'translateY(0)' } },
                slideInRight:  { '0%': { opacity: 0, transform: 'translateX(30px)' },
                                 '100%': { opacity: 1, transform: 'translateX(0)' } },
                scaleIn:       { '0%': { opacity: 0, transform: 'scale(0.9)' },
                                 '100%': { opacity: 1, transform: 'scale(1)' } },
                float:         { '0%,100%': { transform: 'translateY(0)' },
                                 '50%': { transform: 'translateY(-10px)' } },
                shimmer:       { '0%': { backgroundPosition: '-200% 0' },
                                 '100%': { backgroundPosition: '200% 0' } },
            },
            transitionDuration: { 250: '250ms', 350: '350ms' },
        },
    },
    plugins: [
        require('@tailwindcss/forms'),
        require('@tailwindcss/typography'),
        require('@tailwindcss/aspect-ratio'),
    ],
}
