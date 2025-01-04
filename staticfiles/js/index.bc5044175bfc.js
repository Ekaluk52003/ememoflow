
import '../css/tailwind.css';
import '../css/base.css';
import Alpine from 'alpinejs';

Alpine.data('app', () => ({
  open: false,
}));


// Add Alpine object to the window scope
window.Alpine = Alpine

// initialize Alpine
Alpine.start()

window.htmx = require('htmx.org');