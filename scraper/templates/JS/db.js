
var videoDB = (function() {
  var vDB = {};
  var datastore = null;

  /**
   * Open a connection to the datastore.
   */
  vDB.open = function(callback) {
    // Database version.
    var version = 1;

    // Open a connection to the datastore.
    var request = indexedDB.open('videos-db', version);

    // Handle datastore upgrades.
    request.onupgradeneeded = function(e) {
      var db = e.target.result;

      e.target.transaction.onerror = vDB.onerror;

      // Delete the old datastore.
      if (db.objectStoreNames.contains('videos')) {
        db.deleteObjectStore('videos');
      }

      // Create a new datastore.
      var store = db.createObjectStore('videos', {
        keypath: 'id', autoIncrement: true
      });

      store.createIndex('id', 'id', { unique: true });
      store.createIndex('languages', 'languages', { unique: false });
      store.createIndex('title', 'title', { unique: false });
      store.createIndex('speaker', 'speaker', { unique: false });
      store.createIndex('description', 'description', { unique: false });
      
      for (i in json_data){
        var request = store.put(json_data[i]);  
      }
    };

    // Handle successful datastore access.
    request.onsuccess = function(e) {
      // Get a reference to the DB.
      datastore = e.target.result;
      
      // Execute the callback.
      callback();
    };

    // Handle errors when opening the datastore.
    request.onerror = vDB.onerror;
  };


  /**
   * Fetch all of the video items in the datastore.
   * @param {function} callback A function that will be executed once the items
   *                            have been retrieved. Will be passed a param with
   *                            an array of the video items.
   */
  vDB.fetchVideos = function(lower, upper, callback) {
    var db = datastore;
    var transaction = db.transaction(['videos'], 'readwrite');
    var objStore = transaction.objectStore('videos');

    if (lower == 0 && upper == 0){
      var keyRange = IDBKeyRange.lowerBound(0);  
    }
    else {
      var keyRange = IDBKeyRange.bound(lower, upper);  
    }
    
    var cursorRequest = objStore.openCursor(keyRange);

    var videos = [];

    transaction.oncomplete = function(e) {
      // Execute the callback function.
      callback(videos);
    };

    cursorRequest.onsuccess = function(e) {
      var result = e.target.result;
      
      if (!!result == false) {
        return;
      }
      
      videos.push(result.value);
      result.continue();
    };

    cursorRequest.onerror = vDB.onerror;
  };


  /**
   * Create a new video item.
   * @param {string} text The video item.
   */
  vDB.createVideo = function(callback) {
    // Get a reference to the db.
    var db = datastore;

    // Initiate a new transaction.
    var transaction = db.transaction(['videos'], 'readwrite');

    // Get the datastore.
    var objStore = transaction.objectStore('videos');

    
    if(!db.objectStoreNames.contains("videos")) {
      for (i in json_data){
        var request = objStore.put(json_data[i]);  
      }
      // Handle errors.
      request.onerror = vDB.onerror;
    }

    callback();
  };

  // Export the vDB object.
  return vDB;
}());
