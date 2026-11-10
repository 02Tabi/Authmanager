document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Handle Toast Dismissals Securely
    const toastCloseButtons = document.querySelectorAll('.toast-dismiss-btn');
    toastCloseButtons.forEach(function(button) {
        button.addEventListener('click', function(event) {
            // Find the closest parent element with the class 'toast' and remove it
            const toastElement = event.target.closest('.toast');
            if (toastElement) {
                toastElement.remove();
            }
        });
    });

    // 2. Handle Theme Switching Securely
    const themeButtons = document.querySelectorAll('.theme-switch-btn');
    themeButtons.forEach(function(button) {
        button.addEventListener('click', function(event) {
            // Grab the requested theme from the clicked button's data attribute
            const targetButton = event.target.closest('.theme-switch-btn');
            const selectedTheme = targetButton.getAttribute('data-theme');
            
            // Trigger the theme change (assuming your CoreUI theme logic uses this)
            if (typeof window.setTheme === 'function') {
                window.setTheme(selectedTheme);
            } else {
                console.warn('setTheme function is not defined. Ensure CoreUI theme scripts are loaded.');
            }
        });
    });

});

document.addEventListener('DOMContentLoaded', () => {
    
    // --- THEME SWITCHER LOGIC ---
    const themeButtons = document.querySelectorAll('.theme-switch-btn');
    const themeIcon = document.getElementById('themeIcon');
    
    // Function to update the header icon
    const updateThemeIcon = (theme) => {
        if (!themeIcon) return;
        if (theme === 'light') {
            themeIcon.innerHTML = '<use xlink:href="#cil-sun"></use>';
        } else if (theme === 'dark') {
            themeIcon.innerHTML = '<use xlink:href="#cil-moon"></use>';
        } else {
            themeIcon.innerHTML = '<use xlink:href="#cil-contrast"></use>';
        }
    };

    // Function to apply the theme
    const setTheme = (theme) => {
        // CoreUI standard uses data-coreui-theme on the html tag
        if (theme === 'auto') {
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-coreui-theme', isDark ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-coreui-theme', theme);
        }
        
        // Save preference and update icon
        localStorage.setItem('preferred_theme', theme);
        updateThemeIcon(theme);
    };

    // 1. Initialize theme on page load based on saved preference (or default to auto)
    const storedTheme = localStorage.getItem('preferred_theme') || 'auto';
    setTheme(storedTheme);

    // 2. Add click listeners to the dropdown buttons
    themeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const theme = btn.getAttribute('data-theme');
            setTheme(theme);
        });
    });
    
});

// SECURITY FIX FOR AUTH-005: Convert GET links to POST requests automatically
document.addEventListener('DOMContentLoaded', function() {
    const postLinks = document.querySelectorAll('a.js-post-link');
    
    postLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault(); // Stop the unsafe GET request

            // Optional confirmation dialog
            const confirmMsg = this.getAttribute('data-confirm');
            if (confirmMsg && !confirm(confirmMsg)) {
                return;
            }

            // Create a hidden form dynamically
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = this.getAttribute('href');
            form.style.display = 'none';

            // Get the CSRF token from the hidden input we added to the HTML
            const csrfTokenElement = document.getElementById('global-csrf-token');
            const tokenValue = csrfTokenElement ? csrfTokenElement.value : '';

            // Inject Django's CSRF token directly
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = tokenValue;
            form.appendChild(csrfInput);

            // Append to body and submit
            document.body.appendChild(form);
            form.submit();
        });
    });
});
