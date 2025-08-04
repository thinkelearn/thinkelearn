# Gallery Lightbox Testing

## Overview

This document describes how to test the gallery lightbox functionality to ensure it works correctly and prevent regressions.

## Simple Test Script

The main test is a standalone script that:

- Starts a Django development server
- Uses Playwright to test gallery functionality
- Provides clear pass/fail results
- Automatically handles Playwright installation

### Usage

```bash
# From project root directory
python tests/test_gallery.py
```

### What it tests

- ✅ Looks specifically for a "Sample Gallery" showcase page
- ✅ GLightbox library loads on gallery pages
- ✅ Gallery items don't navigate directly to image URLs
- ✅ Lightbox opens when clicking gallery items
- ✅ Lightbox closes with Escape key
- ✅ Gracefully passes if no "Sample Gallery" page exists

### Test Results

- **PASSED**: Gallery functionality working correctly
- **PASSED**: No gallery functionality found (nothing to break)
- **FAILED**: Gallery navigates to image URLs instead of opening lightbox

## Creating Gallery Content for Testing

To create the required test content:

1. **Create a Showcase Page** titled exactly **"Sample Gallery"** through the admin
2. **Add gallery content** using the gallery content block with multiple images
3. **Run the test** to verify the lightbox functionality works

The test specifically looks for `/showcase/sample-gallery/` URL path.

## Integration with CI/CD

The test is **excluded from CI by default** to keep the pipeline simple and fast. This is a manual test for verifying gallery functionality during development.

## Requirements

- `uv` package manager
- Playwright (auto-installed by the test script)
- Django development server capability

## Test Philosophy

This test focuses on **user experience** rather than complex data setup:

- Tests against real pages in the application
- Gracefully handles missing content
- Provides actionable feedback
- Simple to run and understand

The approach prioritizes **practical regression testing** over comprehensive coverage.
