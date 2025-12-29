"""
Integration tests for navigation dropdown accessibility.

Tests verify:
- Click-to-toggle functionality
- Outside click closes dropdown
- Keyboard navigation (Enter, Space, Arrow keys, Escape, Tab)
- ARIA attributes are set correctly
- Focus management follows WAI-ARIA patterns
"""

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def authenticated_page(page: Page):
    """Navigate to site with authenticated user."""
    # Navigate to login page
    page.goto("http://localhost:8000/accounts/login/")

    # Fill in credentials (adjust as needed for your test user)
    page.fill('input[name="login"]', "felavid@gmail.com")
    page.fill('input[name="password"]', "WZV-bcv4fga5cga8mum")

    # Submit login form
    page.click('button[type="submit"]')

    # Wait for redirect to dashboard or home
    page.wait_for_url("**/*", wait_until="networkidle")

    return page


class TestNavigationDropdown:
    """Test suite for user dropdown menu accessibility."""

    def test_dropdown_button_has_aria_attributes(self, authenticated_page: Page):
        """Verify ARIA attributes are present on button."""
        button = authenticated_page.locator("#user-menu-button")

        # Check initial state
        expect(button).to_have_attribute("aria-expanded", "false")
        expect(button).to_have_attribute("aria-haspopup", "true")
        expect(button).to_have_attribute("aria-controls", "user-menu-dropdown")

    def test_dropdown_menu_has_role_attribute(self, authenticated_page: Page):
        """Verify dropdown has proper role."""
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        expect(dropdown).to_have_attribute("role", "menu")
        expect(dropdown).to_have_attribute("aria-orientation", "vertical")
        expect(dropdown).to_have_attribute("aria-labelledby", "user-menu-button")

    def test_menu_items_have_role_menuitem(self, authenticated_page: Page):
        """Verify menu items have proper role."""
        menu_items = authenticated_page.locator(
            '#user-menu-dropdown a[role="menuitem"]'
        )

        # Should have 3 menu items: Dashboard, Account Settings, Sign Out
        expect(menu_items).to_have_count(3)

    def test_dropdown_opens_on_click(self, authenticated_page: Page):
        """Verify dropdown opens when button is clicked."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Initially hidden
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
        expect(button).to_have_attribute("aria-expanded", "false")

        # Click to open
        button.click()

        # Dropdown should be visible (no 'hidden' class)
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))
        expect(button).to_have_attribute("aria-expanded", "true")

    def test_dropdown_closes_on_second_click(self, authenticated_page: Page):
        """Verify dropdown closes when button is clicked again."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Open dropdown
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # Click again to close
        button.click()
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
        expect(button).to_have_attribute("aria-expanded", "false")

    def test_dropdown_closes_on_outside_click(self, authenticated_page: Page):
        """Verify dropdown closes when clicking outside."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Open dropdown
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # Click outside (on the main heading or body)
        authenticated_page.locator("body").click(position={"x": 10, "y": 10})

        # Dropdown should close
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
        expect(button).to_have_attribute("aria-expanded", "false")

    def test_chevron_rotates_when_dropdown_opens(self, authenticated_page: Page):
        """Verify chevron icon rotates when dropdown opens."""
        button = authenticated_page.locator("#user-menu-button")
        icon = authenticated_page.locator("#user-menu-icon")

        # Open dropdown
        button.click()

        # Icon should rotate to 180deg
        rotated_transform = icon.evaluate("el => el.style.transform")
        assert "rotate(180deg)" in rotated_transform

        # Close dropdown
        button.click()

        # Icon should rotate back to 0deg
        final_transform = icon.evaluate("el => el.style.transform")
        assert "rotate(0deg)" in final_transform

    def test_keyboard_enter_toggles_dropdown(self, authenticated_page: Page):
        """Verify Enter key toggles dropdown."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Focus button
        button.focus()

        # Press Enter to open
        authenticated_page.keyboard.press("Enter")
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # Press Enter again to close
        authenticated_page.keyboard.press("Enter")
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))

    def test_keyboard_space_toggles_dropdown(self, authenticated_page: Page):
        """Verify Space key toggles dropdown."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Focus button
        button.focus()

        # Press Space to open
        authenticated_page.keyboard.press("Space")
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # Press Space again to close
        authenticated_page.keyboard.press("Space")
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))

    def test_keyboard_escape_closes_dropdown(self, authenticated_page: Page):
        """Verify Escape key closes dropdown and returns focus."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Open dropdown
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # Press Escape
        authenticated_page.keyboard.press("Escape")

        # Dropdown should close
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))

        # Focus should return to button
        expect(button).to_be_focused()

    def test_keyboard_arrow_down_opens_and_focuses_first_item(
        self, authenticated_page: Page
    ):
        """Verify Arrow Down opens dropdown and focuses first menu item."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")
        first_item = authenticated_page.locator(
            '#user-menu-dropdown a[role="menuitem"]'
        ).first

        # Focus button
        button.focus()

        # Press Arrow Down
        authenticated_page.keyboard.press("ArrowDown")

        # Dropdown should open
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # First menu item should have focus
        expect(first_item).to_be_focused()

    def test_keyboard_arrow_navigation_within_menu(self, authenticated_page: Page):
        """Verify Arrow Up/Down navigates between menu items."""
        button = authenticated_page.locator("#user-menu-button")
        menu_items = authenticated_page.locator(
            '#user-menu-dropdown a[role="menuitem"]'
        )

        # Open dropdown
        button.click()

        # Focus first item
        menu_items.first.focus()

        # Press Arrow Down
        authenticated_page.keyboard.press("ArrowDown")
        expect(menu_items.nth(1)).to_be_focused()  # Second item (Account Settings)

        # Press Arrow Down again
        authenticated_page.keyboard.press("ArrowDown")
        expect(menu_items.nth(2)).to_be_focused()  # Third item (Sign Out)

        # Press Arrow Up
        authenticated_page.keyboard.press("ArrowUp")
        expect(menu_items.nth(1)).to_be_focused()  # Back to second item

    def test_keyboard_arrow_navigation_wraps_around(self, authenticated_page: Page):
        """Verify arrow navigation wraps from last to first and vice versa."""
        button = authenticated_page.locator("#user-menu-button")
        menu_items = authenticated_page.locator(
            '#user-menu-dropdown a[role="menuitem"]'
        )

        # Open dropdown
        button.click()

        # Focus first item and press Arrow Up (should wrap to last)
        menu_items.first.focus()
        authenticated_page.keyboard.press("ArrowUp")
        expect(menu_items.last).to_be_focused()

        # Press Arrow Down (should wrap to first)
        authenticated_page.keyboard.press("ArrowDown")
        expect(menu_items.first).to_be_focused()

    def test_keyboard_tab_closes_dropdown(self, authenticated_page: Page):
        """Verify Tab key closes dropdown."""
        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Open dropdown
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # Focus a menu item
        dropdown.locator('a[role="menuitem"]').first.focus()

        # Press Tab
        authenticated_page.keyboard.press("Tab")

        # Dropdown should close
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))

    def test_dropdown_works_on_mobile_viewport(self, authenticated_page: Page):
        """Verify dropdown works on mobile viewport."""
        # Set mobile viewport
        authenticated_page.set_viewport_size({"width": 375, "height": 667})

        button = authenticated_page.locator("#user-menu-button")
        dropdown = authenticated_page.locator("#user-menu-dropdown")

        # Click to open
        button.click()
        expect(dropdown).not_to_have_class(re.compile(r"\bhidden\b"))

        # Click to close
        button.click()
        expect(dropdown).to_have_class(re.compile(r"\bhidden\b"))
