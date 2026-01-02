# Tailwind CSS Quick Reference

## Critical Concept: Content Scanning

**Tailwind only generates CSS for classes it finds in your files.**

If a Tailwind class doesn't work, it's usually because:
1. The file isn't in the `content` array in `tailwind.config.js`
2. The class uses dynamic strings (which Tailwind can't detect)

### Current Content Paths

```javascript
// tailwind.config.js
content: [
  './thinkelearn/templates/**/*.html',
  './home/templates/**/*.html',
  './search/templates/**/*.html',
  './blog/templates/**/*.html',
  './portfolio/templates/**/*.html',
  './lms/templates/**/*.html',           // ← Added for LMS
  './payments/templates/**/*.html',       // ← Added for payments
  './communications/templates/**/*.html', // ← Added for communications
  './thinkelearn/static/js/**/*.js',
],
```

**Rule**: When you create a new Django app with templates, **add it to this list immediately**.

## Development Workflow

### Local Development (Docker)

The CSS builder service auto-watches and rebuilds:

```bash
# Start everything (CSS watch mode enabled)
./start.sh

# CSS rebuilds automatically when you:
# - Edit any template in the content paths
# - Change tailwind.config.js
# - Modify input.css

# View CSS builder logs
docker-compose logs -f css
```

**Expected behavior:**
- Save template → CSS rebuilds in ~1 second
- Hard refresh browser (Cmd+Shift+R) → See changes immediately
- NO need to restart containers for template/CSS changes

### Production Build

```bash
# Local production build
npm run build-css-prod

# Docker production build (what Railway uses)
docker-compose exec web npm run build-css-prod

# Inside Railway/nixpacks (automatic)
# Happens during deployment via nixpacks.toml
```

## Common Issues & Solutions

### Issue: "My Tailwind classes aren't working"

**Check 1**: Is the template directory in `tailwind.config.js`?

```bash
# Quick check - does your template path appear?
grep -A 10 "content:" tailwind.config.js
```

**Fix**: Add the missing directory:

```javascript
content: [
  // ... existing paths
  './your_new_app/templates/**/*.html',
],
```

**Check 2**: Are you using dynamic class names?

```html
<!-- ❌ BAD - Tailwind can't detect this -->
<div class="text-{{ color }}-500">

<!-- ✅ GOOD - Full class name -->
<div class="text-red-500">

<!-- ✅ GOOD - Use conditionals with full class names -->
<div class="{% if error %}text-red-500{% else %}text-green-500{% endif %}">
```

**Check 3**: Did you hard refresh?

```
Cmd + Shift + R (Mac)
Ctrl + Shift + R (Windows/Linux)
```

### Issue: "CSS changes aren't showing up"

**For local development:**

```bash
# 1. Check if CSS watcher is running
docker-compose logs -f css

# 2. Restart CSS service if needed
docker-compose restart css

# 3. Nuclear option - rebuild everything
./start.sh rebuild

# 4. Check browser isn't caching old CSS
# Open DevTools (F12) → Network tab → Disable cache
```

**For production (Railway):**

```bash
# CSS is built during deployment
# Check build logs for errors:
railway logs

# If CSS seems wrong, trigger redeploy:
railway redeploy
```

### Issue: "Classes work locally but not in production"

This happens when:
1. Local has old CSS with unused classes still present
2. Production builds clean CSS without those classes
3. You forgot to add the template directory to `content`

**Solution:**

```bash
# 1. Add directory to tailwind.config.js content array
# 2. Test with production build locally:
npm run build-css-prod

# 3. Check output file:
ls -lh thinkelearn/static/css/thinkelearn.css

# 4. If classes missing, they weren't detected - check content paths
```

## File Locations

```
thinkelearn/
├── tailwind.config.js          # Content paths and theme config
├── package.json                # NPM scripts (build-css, build-css-prod)
├── thinkelearn/static/css/
│   ├── src/input.css          # Source file (@tailwind directives)
│   └── thinkelearn.css        # Generated output (don't edit!)
└── docker-compose.yml          # CSS service with --watch
```

## NPM Scripts

```bash
# Development build (not minified, includes dev features)
npm run build-css

# Production build (minified, optimized)
npm run build-css-prod
```

## Adding Custom Colors/Styles

### Custom Colors (extends default palette)

```javascript
// tailwind.config.js
theme: {
  extend: {
    colors: {
      'brand-blue': '#1234AB',  // Simple color
      primary: {                 // Color palette
        50: '#f7f4f3',
        100: '#ede6e3',
        // ... up to 900
      },
    },
  },
},
```

**Use in templates:**

```html
<div class="bg-brand-blue">Simple color</div>
<div class="bg-primary-50">Palette color</div>
<div class="hover:bg-primary-600">With variants</div>
```

### Custom Spacing

```javascript
// tailwind.config.js
theme: {
  extend: {
    spacing: {
      '128': '32rem',
      '144': '36rem',
    },
  },
},
```

### Custom Fonts

Already configured:

```javascript
fontFamily: {
  sans: ['Inter', 'system-ui', 'sans-serif'],      // Default
  heading: ['Poppins', 'system-ui', 'sans-serif'], // Headings
},
```

**Use in templates:**

```html
<h1 class="font-heading">Uses Poppins</h1>
<p class="font-sans">Uses Inter (default)</p>
```

## Tailwind Design System (THINK eLearn)

### Brand Colors

```html
<!-- Primary: Warm brown (headers/navigation) -->
<header class="bg-primary-800 text-white">
<h1 class="text-primary-800">

<!-- Secondary: Orange (CTAs/links) -->
<button class="bg-secondary-500 hover:bg-secondary-600">
<a href="#" class="text-secondary-500">

<!-- Accent: Mint/Cyan (modern sections) -->
<section class="bg-cyan-50">
<div class="bg-cyan-600 text-white">

<!-- Neutral: Warm gray (body text/backgrounds) -->
<p class="text-neutral-700">
<div class="bg-neutral-50">
<div class="border-neutral-200">
```

### Common Patterns

```html
<!-- Primary Button -->
<button class="bg-secondary-500 hover:bg-secondary-600 text-white px-6 py-3 rounded-md">

<!-- Card -->
<div class="bg-white rounded-lg shadow-md p-6">

<!-- Section Container -->
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

<!-- Gradient Header -->
<div class="bg-gradient-to-r from-primary-800 to-primary-700 text-white py-16">
```

## Troubleshooting Checklist

When Tailwind classes don't work:

- [ ] Is the template directory in `content` array?
- [ ] Are you using full class names (not dynamic strings)?
- [ ] Did you hard refresh the browser?
- [ ] Is the CSS watcher running? (`docker-compose logs css`)
- [ ] Does the class exist in the output file? (search `thinkelearn.css`)
- [ ] Are you viewing the right page/environment?
- [ ] Did you try restarting the CSS service?

## Quick Commands Reference

```bash
# Development
./start.sh                      # Start with CSS watch mode
docker-compose logs -f css      # Watch CSS rebuild logs
docker-compose restart css      # Restart CSS watcher

# Production build (local)
npm run build-css-prod          # Build minified CSS

# Production build (Railway)
# Automatic via nixpacks.toml during deployment

# Debugging
grep "my-class" thinkelearn/static/css/thinkelearn.css  # Check if class exists
```

## Tips

1. **Always use full class names** - Never construct classes dynamically
2. **Add new apps to content** - Immediately when creating new Django apps
3. **Hard refresh often** - Browser caching can hide CSS changes
4. **Check the CSS service logs** - Errors appear there during rebuild
5. **Test production builds** - Run `npm run build-css-prod` before deploying
6. **Use custom colors** - Don't use arbitrary values like `bg-[#123456]`
7. **Follow the design system** - Use primary/secondary/neutral consistently

## Resources

- [Tailwind Docs - Content Configuration](https://tailwindcss.com/docs/content-configuration)
- [Tailwind Docs - Customization](https://tailwindcss.com/docs/configuration)
- [Tailwind UI Components](https://tailwindui.com/) (paid, but good reference)
- Project: `docs/tailwind-setup.md` (original setup documentation)
