import Alpine from 'alpinejs';

document.addEventListener('alpine:init', () => {
    Alpine.data('userSearch', (initialOptions = []) => ({
        search: '',
        focused: false,
        selected: null,
        options: initialOptions,
        isEditing: true, // Start in editing mode

        get filteredOptions() {
            if (!this.search) return this.options;
            return this.options.filter(option => 
                option.full_name.toLowerCase().includes(this.search.toLowerCase())
            );
        },

        selectUser(option) {
            this.selected = option.id;
            this.search = option.full_name;
            this.focused = false;
            this.isEditing = false;
        },

        startEditing() {
            this.isEditing = true;
            this.focused = true;
            if (this.selected !== null) {
                this.search = '';
                this.selected = null;
            }
        },

        reset() {
            this.search = '';
            this.selected = null;
            this.focused = false;
            this.isEditing = true; // Reset to editing mode
        }
    }));               
  
});
