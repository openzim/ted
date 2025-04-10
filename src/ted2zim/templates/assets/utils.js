// Define storage constants
const NAMESPACE = 'ted2zim';
const SELECTED_LANGUAGE_KEY = `${NAMESPACE}.selectedLanguage`;

// Shared utility functions
const storage = {
  isAvailable: function() {
    try {
      localStorage.setItem('test', 'test');
      localStorage.removeItem('test');
      return true;
    } catch (e) {
      return false;
    }
  },
  setItem: function(key, value) {
    if (this.isAvailable()) {
      localStorage.setItem(key, value);
    }
  },
  getItem: function(key) {
    return this.isAvailable() ? localStorage.getItem(key) : null;
  },
  removeItem: function(key) {
    if (this.isAvailable()) {
      localStorage.removeItem(key);
    }
  }
};
