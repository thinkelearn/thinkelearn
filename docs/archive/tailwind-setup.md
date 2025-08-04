# Tailwind CSS Integration with Wagtail

## Installation & Setup

### Dependencies

```bash
npm install -D tailwindcss @tailwindcss/typography @tailwindcss/forms
npx tailwindcss init
```

### Configuration

The `tailwind.config.js` file extends Tailwind with our custom brand colors and typography:

- **Content paths**: Configured to scan all Django templates and static JS files
- **Custom colors**: Warm earth tone palette (brown primary, orange secondary, neutral grays)
- **Typography**: Inter for body text, Poppins for headings
- **Plugins**: Typography plugin for rich text, Forms plugin for styled form controls

### Build Process

```bash
# Development (watch mode)
npm run build-css

# Production (minified)
npm run build-css-prod
```

### CSS Structure

Source: `thinkelearn/static/css/src/input.css`
Output: `thinkelearn/static/css/thinkelearn.css`

Custom layers:

- **Base**: Typography defaults and responsive text sizing
- **Components**: Reusable UI components (buttons, cards, sections)
- **Utilities**: Custom utility classes for common patterns

## Design System

### Color Palette

- **Primary (Brown)**: Professional, educational feel. Use for headers, navigation, dark text
- **Secondary (Orange)**: Brand accent from logo. Use for CTAs, links, highlights
- **Neutral**: Warm grays that harmonize with brown palette. Use for body text, backgrounds, borders

### Usage Guidelines

- Headers/Navigation: `text-primary-800` or `bg-primary-800`
- CTAs/Buttons: `bg-secondary-500 hover:bg-secondary-600`
- Links: `text-secondary-500 hover:text-secondary-600`
- Body text: `text-neutral-700`
- Backgrounds: `bg-neutral-50` (light), `bg-primary-50` (warm tint)

### Component Classes

- `.btn`: Base button styling with variants
- `.card` / `.card-hover`: Container components
- `.section-padding`: Consistent vertical spacing
- `.hero-gradient`: Brand gradient for hero sections

## Development Workflow

1. Start CSS build: `npm run build-css` (watches for changes)
2. Start Django server: `python manage.py runserver`
3. Edit templates - Tailwind auto-rebuilds CSS
4. Production build: `npm run build-css-prod` before deployment

## Responsive Design

Mobile-first approach using Tailwind's responsive prefixes:

- `sm:` 640px+ (large phones)
- `md:` 768px+ (tablets)
- `lg:` 1024px+ (laptops)
- `xl:` 1280px+ (desktops)
