
import '../css/tailwind.css';
import '../css/base.css';
import Alpine from 'alpinejs';
import htmx from 'htmx.org';

// Initialize Alpine.js
window.Alpine = Alpine;
Alpine.start();

// Optionally, make HTMX available globally (if needed)
window.htmx = htmx;