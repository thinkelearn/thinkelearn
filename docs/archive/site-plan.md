# THINK eLearn Website Plan

## Project Overview

Build a modern, stateless website for THINK eLearn to be hosted at thinkelearn.com using Railway. The site will leverage Wagtail CMS for content management and Tailwind CSS for styling.

## Core Pages & Features

### 1. Homepage

- **Purpose**: Landing page with clear value proposition
- **Content**: Hero section, key features, call-to-action
- **Wagtail Model**: Enhanced `HomePage` with rich content fields
- **Key Elements**:
  - Hero banner with tagline
  - Feature highlights
  - Testimonials/social proof
  - Newsletter signup
  - Recent blog posts preview

### 2. About Us

- **Purpose**: Company story, mission, values
- **Content**: Team bios, company history, values
- **Wagtail Model**: `AboutPage` with team member snippets
- **Key Elements**:
  - Company story
  - Team member cards
  - Mission & values
  - Timeline/milestones

### 3. Portfolio/Showcase

- **Purpose**: Showcase projects, case studies, success stories
- **Content**: Project galleries, case studies
- **Wagtail Model**: `PortfolioIndexPage` with `ProjectPage` children
- **Key Elements**:
  - Project grid/gallery
  - Case study details
  - Client testimonials
  - Project categories/filters

### 4. Blog

- **Purpose**: Content marketing, thought leadership
- **Content**: Articles, tutorials, industry insights
- **Wagtail Model**: `BlogIndexPage` with `BlogPage` children
- **Key Elements**:
  - Article listing with pagination
  - Categories and tags
  - Author profiles
  - Related posts
  - Search functionality

### 5. Contact

- **Purpose**: Lead generation, customer support
- **Content**: Contact form, office locations, social links
- **Wagtail Model**: `ContactPage` with form functionality
- **Key Elements**:
  - Contact form
  - Office locations/map
  - Social media links
  - FAQ section

### 6. Services/Courses (Future)

- **Purpose**: Service offerings, course catalog
- **Content**: Service descriptions, pricing, course listings
- **Wagtail Model**: `ServiceIndexPage` and `ServicePage`

## Technical Architecture

### Wagtail Design Principles

- **Stateless**: No user sessions, minimal server state
- **Page-based**: Each major section as a Wagtail page type
- **Content-first**: Rich text fields, image galleries, structured content
- **SEO-friendly**: Meta fields, structured data, clean URLs
- **Performance**: Image optimization, caching, CDN-ready

### Styling with Tailwind CSS

- **Responsive**: Mobile-first design
- **Component-based**: Reusable UI components
- **Utility-first**: Tailwind utility classes
- **Custom theme**: Brand colors, typography, spacing
- **Dark mode**: Optional dark theme support

### Deployment on Railway

- **Database**: PostgreSQL (Railway managed)
- **Static files**: Whitenoise for static file serving
- **Environment**: Production settings with proper security
- **Domain**: Custom domain thinkelearn.com
- **SSL**: Automatic HTTPS

## Content Strategy

### Homepage Content

- **Hero**: "Empowering Learning Through Innovation"
- **Features**: Key differentiators, benefits
- **Social Proof**: Client logos, testimonials
- **CTA**: "Get Started" or "Learn More"

### Blog Content Topics

- Educational technology trends
- Learning methodologies
- Case studies and success stories
- Industry insights
- How-to guides and tutorials

### Portfolio Content

- Client projects and outcomes
- Before/after transformations
- Process documentation
- Technology stack highlights

## SEO & Performance

- **Meta tags**: Title, description, keywords
- **Structured data**: JSON-LD for rich snippets
- **Image optimization**: WebP format, responsive images
- **Page speed**: Optimized assets, lazy loading
- **Mobile-first**: Responsive design principles

## Analytics & Tracking

- **Google Analytics**: Page views, user behavior
- **Contact form**: Lead tracking
- **Performance monitoring**: Core Web Vitals
- **Error tracking**: 404s, server errors

## Development Phases

### Phase 1: Foundation

1. Set up Tailwind CSS integration
2. Create base page models
3. Design system components
4. Homepage development

### Phase 2: Core Pages

1. About Us page
2. Contact page with form
3. Basic blog functionality
4. Navigation and footer

### Phase 3: Advanced Features

1. Portfolio/showcase section
2. Advanced blog features
3. SEO optimization
4. Performance tuning

### Phase 4: Launch & Optimization

1. Railway deployment setup
2. Domain configuration
3. Analytics setup
4. Performance monitoring

## Next Steps

1. Set up Tailwind CSS in the Django project
2. Create custom Wagtail page models
3. Design and implement base templates
4. Develop homepage with hero section
5. Set up Railway deployment pipeline
