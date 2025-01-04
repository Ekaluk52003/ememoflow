import 'htmx.org';
import 'alpinejs';
import '../css/tailwind.css';


import Quill from 'quill';
import 'quill/dist/quill.snow.css';  // Optional: Include Quill's CSS for the Snow theme

// Example: Initialize Quill
var quill = new Quill('#editor', {
  theme: 'snow'
});

