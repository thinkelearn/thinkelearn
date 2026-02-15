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
    initTopbarScroll();
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

    // Reposition dropdown on scroll/resize
    window.addEventListener('scroll', repositionDropdown, { passive: true });
    window.addEventListener('resize', repositionDropdown);

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
     * Calculate and set dropdown position relative to button
     */
    function positionDropdown() {
        const buttonRect = userMenuButton.getBoundingClientRect();
        userMenuDropdown.style.top = `${buttonRect.bottom}px`;
        userMenuDropdown.style.right = `${window.innerWidth - buttonRect.right}px`;
    }

    /**
     * Reposition dropdown menu if it's open
     */
    function repositionDropdown() {
        if (userMenuButton.getAttribute('aria-expanded') === 'true') {
            positionDropdown();
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
        // Position dropdown relative to button
        positionDropdown();

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

/**
 * Hide the topbar on scroll down and reveal it when at the top.
 *
 * Uses transform: translateY() instead of max-height to avoid layout reflow.
 * The topbar slides up behind the viewport edge without changing the sticky
 * container's layout height, preventing the scroll-position feedback loop
 * that caused jitter near the top of the page.
 */
function initTopbarScroll() {
    const wrapper = document.getElementById('topbar-wrapper');
    const topbar = document.getElementById('topbar-container');

    if (!wrapper || !topbar) {
        return;
    }

    let isHidden = false;
    let ticking = false;

    // Hide once scrolled past this point (px).
    // Must be larger than the topbar height (40px) to avoid feedback loops.
    const HIDE_THRESHOLD = 50;
    // Show only when within this distance from the top (px)
    const SHOW_THRESHOLD = 10;

    function update() {
        const currentScrollY = window.scrollY;

        if (!isHidden && currentScrollY > HIDE_THRESHOLD) {
            isHidden = true;
            topbar.style.transform = 'translateY(-100%)';
            wrapper.style.height = '0';
        } else if (isHidden && currentScrollY <= SHOW_THRESHOLD) {
            isHidden = false;
            topbar.style.transform = '';
            wrapper.style.height = '2.5rem';
        }

        ticking = false;
    }

    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(update);
            ticking = true;
        }
    }, { passive: true });
}
