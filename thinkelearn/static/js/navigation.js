/**
 * Navigation component - Mobile menu and user dropdown
 *
 * Handles:
 * - Mobile hamburger menu toggle
 * - User dropdown menu with click-to-toggle
 * - Keyboard navigation (WAI-ARIA compliant)
 * - Outside click detection
 * - Focus management
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize both navigation components
    initMobileMenu();
    initUserDropdown();
});

/**
 * Mobile hamburger menu toggle
 */
function initMobileMenu() {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', function() {
            mobileMenu.classList.toggle('hidden');
        });
    }
}

/**
 * User dropdown menu with accessibility features
 */
function initUserDropdown() {
    const userMenuButton = document.getElementById('user-menu-button');
    const userMenuDropdown = document.getElementById('user-menu-dropdown');
    const userMenuIcon = document.getElementById('user-menu-icon');

    // Constants
    const MENU_ITEM_SELECTOR = 'a[role="menuitem"]';
    const CHEVRON_ROTATION_OPEN = '180deg';
    const CHEVRON_ROTATION_CLOSED = '0deg';

    if (!userMenuButton || !userMenuDropdown) {
        return; // Elements not found (user not authenticated)
    }

    // Click handler for button
    userMenuButton.addEventListener('click', handleButtonClick);

    // Outside click handler
    document.addEventListener('click', handleOutsideClick);

    // Keyboard navigation handlers
    userMenuButton.addEventListener('keydown', handleButtonKeydown);
    userMenuDropdown.addEventListener('keydown', handleMenuKeydown);

    /**
     * Toggle dropdown on button click
     */
    function handleButtonClick(e) {
        e.stopPropagation();
        const isExpanded = userMenuButton.getAttribute('aria-expanded') === 'true';

        if (isExpanded) {
            closeUserMenu();
        } else {
            openUserMenu();
        }
    }

    /**
     * Close dropdown when clicking outside
     */
    function handleOutsideClick(e) {
        if (e.target &&
            !userMenuButton.contains(e.target) &&
            !userMenuDropdown.contains(e.target)) {
            closeUserMenu();
        }
    }

    /**
     * Handle keyboard events on button
     */
    function handleButtonKeydown(e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            const isExpanded = userMenuButton.getAttribute('aria-expanded') === 'true';

            if (isExpanded) {
                closeUserMenu();
            } else {
                openUserMenu();
            }
        } else if (e.key === 'Escape') {
            closeUserMenu();
            userMenuButton.focus();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();

            if (userMenuButton.getAttribute('aria-expanded') !== 'true') {
                openUserMenu();
            }

            // Focus first menu item
            const firstMenuItem = userMenuDropdown.querySelector(MENU_ITEM_SELECTOR);
            if (firstMenuItem) {
                firstMenuItem.focus();
            }
        }
    }

    /**
     * Handle keyboard navigation within dropdown menu
     */
    function handleMenuKeydown(e) {
        const menuItems = Array.from(userMenuDropdown.querySelectorAll(MENU_ITEM_SELECTOR));
        const currentIndex = menuItems.indexOf(document.activeElement);

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            const nextIndex = currentIndex < menuItems.length - 1 ? currentIndex + 1 : 0;
            menuItems[nextIndex].focus();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            const prevIndex = currentIndex > 0 ? currentIndex - 1 : menuItems.length - 1;
            menuItems[prevIndex].focus();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            closeUserMenu();
            userMenuButton.focus();
        } else if (e.key === 'Tab') {
            // Close menu when tabbing out
            closeUserMenu();
        }
    }

    /**
     * Open user menu and update ARIA state
     */
    function openUserMenu() {
        userMenuDropdown.classList.remove('hidden');
        userMenuButton.setAttribute('aria-expanded', 'true');

        if (userMenuIcon) {
            userMenuIcon.style.transform = `rotate(${CHEVRON_ROTATION_OPEN})`;
        }
    }

    /**
     * Close user menu and update ARIA state
     */
    function closeUserMenu() {
        userMenuDropdown.classList.add('hidden');
        userMenuButton.setAttribute('aria-expanded', 'false');

        if (userMenuIcon) {
            userMenuIcon.style.transform = `rotate(${CHEVRON_ROTATION_CLOSED})`;
        }
    }
}
