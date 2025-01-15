import 'htmx.org';
import 'alpinejs';
// import '../css/tailwind.css';
import '../css/base.css';

import Alpine from 'alpinejs';

Alpine.data('app', () => ({
  open: false,
}));

window.Alpine = Alpine;
Alpine.start();