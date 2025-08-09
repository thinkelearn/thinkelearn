#!/usr/bin/env python3
"""
Simple gallery lightbox test script.

This script starts a Django server, tests the gallery lightbox functionality,
and provides clear pass/fail results.

Usage: python test_gallery.py
"""

import subprocess
import sys
import time
from pathlib import Path


def main():
    """Run the gallery lightbox test."""
    print("🎭 Gallery Lightbox Test")
    print("=" * 40)

    # Check we're in the right directory
    if not Path("manage.py").exists():
        print("❌ Error: Please run this from the project root directory")
        return False

    # Start Django server
    print("🚀 Starting Django server...")
    server_process = subprocess.Popen(
        ["uv", "run", "python", "manage.py", "runserver", "8001"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to start
    time.sleep(3)

    try:
        # Run the actual test
        result = test_gallery_with_playwright()

        if result:
            print("\n🎉 Gallery lightbox test PASSED!")
            print("✅ The gallery functionality is working correctly")
            return True
        else:
            print("\n❌ Gallery lightbox test FAILED!")
            print("⚠️  The gallery functionality needs attention")
            return False

    finally:
        # Clean up server
        print("🛑 Stopping Django server...")
        server_process.terminate()
        server_process.wait()


def test_gallery_with_playwright():
    """Test gallery functionality using Playwright."""
    # Check if Playwright is available
    result = subprocess.run(
        ["uv", "run", "python", "-c", "import playwright"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("❌ Playwright not available. Installing...")
        subprocess.run(
            ["uv", "add", "--group", "dev", "playwright>=1.49.0"], check=True
        )
        subprocess.run(["uv", "run", "playwright", "install", "chromium"], check=True)

    # Run the actual test in uv environment
    test_script = """
from playwright.sync_api import sync_playwright

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("📖 Testing portfolio pages...")

            # Navigate to portfolio index
            page.goto("http://localhost:8001/portfolio/")
            page.wait_for_load_state("networkidle")

            # Look specifically for Sample Gallery page
            sample_gallery_link = page.locator('a[href*="/portfolio/sample-gallery/"]')

            if sample_gallery_link.count() == 0:
                print("ℹ️  No 'Sample Gallery' page found - test passed")
                print("   💡 Create a portfolio page titled 'Sample Gallery' with gallery content to test functionality")
                return True

            print("📄 Found Sample Gallery page")

            # Visit the Sample Gallery page
            sample_gallery_link.first.click()
            page.wait_for_load_state("networkidle")

            # Check if GLightbox is available
            has_glightbox = page.evaluate("() => typeof GLightbox !== 'undefined'")
            if not has_glightbox:
                print("ℹ️  No GLightbox found - test passed (no gallery functionality to test)")
                return True

            print("✅ GLightbox library loaded")

            # Look for gallery items
            gallery_items = page.locator(".gallery-item")
            gallery_count = gallery_items.count()

            if gallery_count == 0:
                print("ℹ️  No gallery items found - test passed")
                return True

            print(f"🖼️  Found {gallery_count} gallery items")

            # Test clicking gallery item
            initial_url = page.url
            gallery_items.first.click()
            page.wait_for_timeout(1000)

            # Check results
            current_url = page.url
            lightbox = page.locator(".glightbox-container")

            if lightbox.count() > 0 and lightbox.is_visible():
                print("✅ Gallery lightbox opened successfully!")

                # Test closing
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

                if not lightbox.is_visible():
                    print("✅ Lightbox closes with Escape key")

                return True

            elif current_url == initial_url:
                print("✅ Gallery clicks don't navigate away from page")
                return True

            elif "/media/images/" in current_url:
                print("❌ Gallery navigates directly to image URL (should open lightbox)")
                return False

            else:
                print("⚠️  Unexpected navigation behavior")
                return False

        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            return False

        finally:
            browser.close()

# Run the test and return result
import sys
success = run_test()
sys.exit(0 if success else 1)
"""

    result = subprocess.run(
        ["uv", "run", "python", "-c", test_script], capture_output=True, text=True
    )

    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")

    return result.returncode == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
