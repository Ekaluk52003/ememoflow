
import '../css/tailwind.css';
import '../css/base.css';
import Alpine from 'alpinejs';


import htmx from 'htmx.org';

// Attach HTMX to the global window object
window.htmx = htmx;

// Optionally, log to confirm it's loaded
console.log('HTMX has been added to the global scope:', window.htmx);

// Initialize Alpine.js
window.Alpine = Alpine;
Alpine.data('app', () => ({
  open: false,
}));





window.htmx = require('htmx.org');