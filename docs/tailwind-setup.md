# Tailwind CSS Integration with Wagtail

## Installation & Setup

### 1. Install Tailwind CSS

```bash
# Install Node.js dependencies
npm init -y
npm install -D tailwindcss @tailwindcss/typography @tailwindcss/forms

# Initialize Tailwind config
npx tailwindcss init
```

### 2. Configure Tailwind

Create `tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './thinkelearn/templates/**/*.html',
    './home/templates/**/*.html',
    './search/templates/**/*.html',
    './thinkelearn/static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors for THINK eLearn
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        secondary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          900: '#14532d',
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
              color: '#3b82f6',
              '&:hover': {
                color: '#1d4ed8',
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
```

### 3. Create CSS Structure

Create `thinkelearn/static/css/src/input.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom base styles */
@layer base {
  body {
    @apply font-sans text-gray-900 leading-relaxed;
  }

  h1, h2, h3, h4, h5, h6 {
    @apply font-heading font-semibold;
  }

  h1 { @apply text-4xl lg:text-5xl; }
  h2 { @apply text-3xl lg:text-4xl; }
  h3 { @apply text-2xl lg:text-3xl; }
  h4 { @apply text-xl lg:text-2xl; }
  h5 { @apply text-lg lg:text-xl; }
  h6 { @apply text-base lg:text-lg; }
}

/* Custom components */
@layer components {
  .btn {
    @apply inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md transition-colors duration-200;
  }

  .btn-primary {
    @apply btn bg-primary-600 text-white hover:bg-primary-700 focus:ring-2 focus:ring-primary-500 focus:ring-offset-2;
  }

  .btn-secondary {
    @apply btn bg-white text-primary-600 border-primary-600 hover:bg-primary-50;
  }

  .btn-outline {
    @apply btn border-gray-300 text-gray-700 hover:bg-gray-50;
  }

  .card {
    @apply bg-white rounded-lg shadow-md overflow-hidden;
  }

  .card-hover {
    @apply card transition-shadow duration-300 hover:shadow-lg;
  }

  .section-padding {
    @apply py-16 lg:py-24;
  }

  .container-padding {
    @apply px-4 sm:px-6 lg:px-8;
  }

  .rich-text {
    @apply prose prose-lg max-w-none;
  }

  .hero-gradient {
    @apply bg-gradient-to-br from-primary-600 via-primary-700 to-primary-800;
  }
}

/* Wagtail admin compatibility */
@layer utilities {
  .wagtail-rich-text {
    @apply rich-text;
  }

  .responsive-image {
    @apply w-full h-auto rounded-lg;
  }
}
```

### 4. Build Process

Add to `package.json`:

```json
{
  "scripts": {
    "build-css": "tailwindcss -i ./thinkelearn/static/css/src/input.css -o ./thinkelearn/static/css/thinkelearn.css --watch",
    "build-css-prod": "tailwindcss -i ./thinkelearn/static/css/src/input.css -o ./thinkelearn/static/css/thinkelearn.css --minify"
  }
}
```

### 5. Django Integration

Update `thinkelearn/settings/base.py`:

```python
# Add to STATICFILES_DIRS
STATICFILES_DIRS = [
    os.path.join(PROJECT_DIR, "static"),
    os.path.join(BASE_DIR, "node_modules"),  # For any node modules if needed
]

# For development - auto-reload CSS changes
if DEBUG:
    STATICFILES_DIRS.append(
        os.path.join(PROJECT_DIR, "static", "css", "src")
    )
```

## Component Library

### Base Template Structure

```html
<!-- base.html -->
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="utf-8">
    <title>{% block title %}{% if page.seo_title %}{{ page.seo_title }}{% else %}{{ page.title }}{% endif %} | THINK eLearn{% endblock %}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{% block description %}{{ page.search_description|default:'Empowering Learning Through Innovation' }}{% endblock %}">

    {% load static %}
    <link rel="stylesheet" href="{% static 'css/thinkelearn.css' %}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">

    {% block extra_css %}{% endblock %}
</head>
<body class="h-full bg-gray-50">
    <div class="min-h-full">
        {% include 'includes/header.html' %}

        <main>
            {% block content %}{% endblock %}
        </main>

        {% include 'includes/footer.html' %}
    </div>

    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Reusable Components

#### Header Component

```html
<!-- includes/header.html -->
<header class="bg-white shadow-sm">
    <nav class="max-w-7xl mx-auto container-padding">
        <div class="flex justify-between items-center h-16">
            <div class="flex items-center">
                <a href="/" class="text-2xl font-heading font-bold text-primary-600">
                    THINK eLearn
                </a>
            </div>

            <div class="hidden md:block">
                <div class="ml-10 flex items-center space-x-8">
                    <a href="/about/" class="text-gray-700 hover:text-primary-600 transition-colors">About</a>
                    <a href="/portfolio/" class="text-gray-700 hover:text-primary-600 transition-colors">Portfolio</a>
                    <a href="/blog/" class="text-gray-700 hover:text-primary-600 transition-colors">Blog</a>
                    <a href="/contact/" class="btn-primary">Contact Us</a>
                </div>
            </div>

            <!-- Mobile menu button -->
            <div class="md:hidden">
                <button type="button" class="text-gray-700 hover:text-primary-600" id="mobile-menu-button">
                    <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </button>
            </div>
        </div>
    </nav>
</header>
```

#### Hero Section Component

```html
<!-- components/hero.html -->
<section class="hero-gradient text-white section-padding">
    <div class="max-w-7xl mx-auto container-padding">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
                <h1 class="text-4xl lg:text-6xl font-heading font-bold mb-6">
                    {{ page.hero_title }}
                </h1>
                {% if page.hero_subtitle %}
                <p class="text-xl lg:text-2xl mb-8 text-primary-100">
                    {{ page.hero_subtitle }}
                </p>
                {% endif %}
                <div class="flex flex-col sm:flex-row gap-4">
                    <a href="{{ page.hero_cta_link.url }}" class="btn bg-white text-primary-600 hover:bg-gray-100">
                        {{ page.hero_cta_text }}
                    </a>
                    <a href="/about/" class="btn border-white text-white hover:bg-white hover:text-primary-600">
                        Learn More
                    </a>
                </div>
            </div>
            {% if page.hero_image %}
            <div class="lg:order-first">
                <img src="{{ page.hero_image.url }}" alt="{{ page.hero_image.alt }}" class="responsive-image">
            </div>
            {% endif %}
        </div>
    </div>
</section>
```

#### Card Components

```html
<!-- components/card.html -->
<div class="card-hover">
    <div class="p-6">
        {% if icon %}
        <div class="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
            <i class="{{ icon }} text-primary-600 text-xl"></i>
        </div>
        {% endif %}
        <h3 class="text-xl font-semibold mb-3">{{ title }}</h3>
        <p class="text-gray-600">{{ description }}</p>
    </div>
</div>
```

## Responsive Design Patterns

### Mobile-First Approach

- Use Tailwind's responsive prefixes: `sm:`, `md:`, `lg:`, `xl:`, `2xl:`
- Start with mobile styles, then enhance for larger screens
- Common breakpoints:
  - `sm`: 640px+ (large phones)
  - `md`: 768px+ (tablets)
  - `lg`: 1024px+ (laptops)
  - `xl`: 1280px+ (desktops)

### Common Responsive Patterns

```html
<!-- Responsive grid -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    <!-- Items -->
</div>

<!-- Responsive text -->
<h1 class="text-2xl md:text-4xl lg:text-5xl">Heading</h1>

<!-- Responsive spacing -->
<section class="py-8 md:py-16 lg:py-24">
    <div class="px-4 md:px-8 lg:px-12">
        <!-- Content -->
    </div>
</section>

<!-- Hide/show on different screens -->
<div class="block md:hidden">Mobile only</div>
<div class="hidden md:block">Desktop only</div>
```

## Performance Optimization

### CSS Purging

Tailwind automatically purges unused CSS in production when configured properly.

### Critical CSS

Consider inlining critical above-the-fold CSS for better performance.

### Build Optimization

```bash
# Development
npm run build-css

# Production
npm run build-css-prod
```

## Development Workflow

1. **Start CSS build process**: `npm run build-css`
2. **Start Django server**: `python manage.py runserver`
3. **Make changes**: Edit templates and CSS
4. **Auto-reload**: Tailwind watches for changes and rebuilds
5. **Production build**: `npm run build-css-prod` before deployment
