// Alpine.js is expected to be loaded on the page already
document.addEventListener('alpine:init', () => {
    // Original userSearch component
    // Signature: userSearch(dataSourceId, preselectedId = null, currentUserId = null)
    Alpine.data('userSearch', (dataSourceId, preselectedId = null, currentUserId = null) => ({
        search: '',
        focused: false,
        selected: null,
        options: [],
        isEditing: true, // Start in editing mode
        showDialog: false, // For dialog-based selection
        selectedUser: null, // Store the selected user object
        currentUserId: currentUserId,
        preselectedId: preselectedId,

        init() {
          // Load data from the script tag after the component is initialized
          const dataEl = document.getElementById(dataSourceId);
          if (dataEl) {
              const allOptions = JSON.parse(dataEl.textContent);
              // Exclude the current user if currentUserId is provided
              this.options = Array.isArray(allOptions)
                ? allOptions.filter(o => this.currentUserId === null || o.id !== this.currentUserId)
                : [];

              // If a preselected approver ID was provided, set it
              if (this.preselectedId !== null) {
                  const pre = this.options.find(o => o.id === this.preselectedId) || allOptions.find(o => o.id === this.preselectedId);
                  if (pre) {
                      this.selected = pre.id;
                      this.selectedUser = pre;
                      this.isEditing = false;
                  }
              }
          } else {
              console.error(`[userSearch] Data source element with ID '${dataSourceId}' not found.`);
          }

          // Notify parent that approver state may have changed
          this.$nextTick(() => {
              this.$dispatch('approver-changed');
          });
      },

      get filteredOptions() {
        if (!this.search) return this.options;
        return this.options.filter(option =>
            option.full_name.toLowerCase().includes(this.search.toLowerCase()) ||
            (option.job_title && option.job_title.toLowerCase().includes(this.search.toLowerCase()))
        );
    },

    selectUser(option) {
      this.selected = option.id;
      this.search = option.full_name;
      this.selectedUser = option;
      this.focused = false;
      this.isEditing = false;
      this.showDialog = false; // Close dialog after selection
      this.$dispatch('approver-changed');
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
            this.selectedUser = null;
            this.focused = false;
            this.isEditing = true; // Reset to editing mode
            this.$dispatch('approver-changed');
        },

       
        // Dialog-specific methods
        openDialog() {
          this.showDialog = true;
          this.search = '';
          // Focus the search input after the dialog is shown
          setTimeout(() => {
              const searchInput = document.getElementById('user-search-dialog-input');
              if (searchInput) searchInput.focus();
          }, 100);
      },
        closeDialog() {
            this.showDialog = false;
        }
    }));

    // CC Recipients component
    Alpine.data('ccRecipients', () => ({
      searchQuery: '',
      searchResults: [],
      selectedUsers: [],
      isLoading: false,
      showDialog: false,
      errorMessage: '',
      documentId: null, // Will be set via x-init in the template

      init() {
        // Initialize selected users from existing hidden inputs
        this.loadExistingUsers();
        // Load authorized users from the document if document ID is available
        if (this.documentId) {
          this.loadDocumentAuthorizedUsers();
        }
      },

      loadDocumentAuthorizedUsers() {
        if (!this.documentId) {
          return;
        }

        const url = `/document/api/document/${this.documentId}/authorized-users/`;

        fetch(url)
          .then(response => {
            if (!response.ok) {
              // If endpoint doesn't exist, don't throw an error
              if (response.status === 404) {
                return { success: true, users: [] };
              }
              throw new Error(`Network response was not ok: ${response.status}`);
            }
            return response.json();
          })
          .then(data => {
            if (data.success && data.users && Array.isArray(data.users)) {
              // Add each authorized user to selectedUsers if not already present
              data.users.forEach(user => {
                if (!this.isUserSelected(user.id)) {
                  this.selectedUsers.push(user);
                  this.addUserToForm(user.id);
                }
              });
            }
          })
          .catch(error => {
            console.error('Error fetching authorized users:', error);
          });
      },

      loadExistingUsers() {
        const container = document.getElementById('cc-recipients-container');
        if (container) {
          const inputs = container.querySelectorAll('input[name="cc_user_ids"]');
          inputs.forEach(input => {
            // Get user details for each ID
            this.fetchUserDetails(input.value);
          });
        }
      },

      loadAuthorizedUsers() {
        // If we have a document ID, use it to fetch authorized users
        if (this.documentId) {
          this.loadDocumentAuthorizedUsers();
        }
      },

      fetchUserDetails(userId) {
        fetch(`/document/api/user/${userId}/`)
          .then(response => response.json())
          .then(data => {
            if (!this.isUserSelected(data.id)) {
              this.selectedUsers.push(data);
            }
          })
          .catch(error => {
            console.error('Error fetching user details:', error);
          });
      },

      searchUsers() {
        if (this.searchQuery.length < 2) {
          this.searchResults = [];
          return;
        }

        this.isLoading = true;
        fetch(`/document/search-users/?q=${encodeURIComponent(this.searchQuery)}`)
          .then(response => {
            if (!response.ok) {
              throw new Error('Network response was not ok');
            }
            return response.json();
          })
          .then(data => {
            this.searchResults = data.users;
            this.isLoading = false;
          })
          .catch(error => {
            this.errorMessage = 'Failed to search users. Please try again.';
            this.isLoading = false;
            console.error('Error searching users:', error);
          });
      },

      selectUser(user) {
        if (!this.isUserSelected(user.id)) {
          this.selectedUsers.push(user);
          // Create hidden input for the selected user
          this.addUserToForm(user.id);
        }
        this.showDialog = false;
        this.searchQuery = '';
        this.searchResults = [];
      },

      removeUser(userId) {
        this.selectedUsers = this.selectedUsers.filter(user => user.id !== userId);
        // Remove hidden input for the user
        this.removeUserFromForm(userId);
      },

      isUserSelected(userId) {
        return this.selectedUsers.some(user => user.id === userId);
      },

      addUserToForm(userId) {
        const container = document.getElementById('cc-recipients-container');
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'cc_user_ids';
        input.value = userId;
        input.id = `cc-user-${userId}`;
        container.appendChild(input);
      },

      removeUserFromForm(userId) {
        const input = document.getElementById(`cc-user-${userId}`);
        if (input) {
          input.remove();
        }
      },

      openDialog() {
        this.showDialog = true;
        this.searchQuery = '';
        this.searchResults = [];
        this.errorMessage = '';
        // Focus the search input after the dialog is shown
        setTimeout(() => {
          document.getElementById('user-search-input').focus();
        }, 100);
      },

      closeDialog() {
        this.showDialog = false;
      }
    }));
});
