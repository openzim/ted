
var videoDb = (function() {
  var vDb = {};
  var datastore = null;

  /**
   * Open a connection to the datastore.
   */
  vDb.open = function(callback) {
    // Database version.
    var version = 1;

    // Open a connection to the datastore.
    var request = indexedDB.open('video-db', version);

    // Handle datastore upgrades.
    request.onupgradeneeded = function(e) {
      var db = e.target.result;

      e.target.transaction.onerror = vDb.onerror;

      // Delete the old datastore.
      if (db.objectStoreNames.contains('videos')) {
        db.deleteObjectStore('videos');
      }

      // Create a new datastore.
      var store = db.createObjectStore('videos', {
        keyPath: 'data'
      });
    };

    // Handle successful datastore access.
    request.onsuccess = function(e) {
      // Get a reference to the DB.
      datastore = e.target.result;
      
      // Execute the callback.
      callback();
    };

    // Handle errors when opening the datastore.
    request.onerror = vDb.onerror;
  };


  /**
   * Fetch all of the todo items in the datastore.
   * @param {function} callback A function that will be executed once the items
   *                            have been retrieved. Will be passed a param with
   *                            an array of the todo items.
   */
  vDb.fetchVideos = function(callback) {
    var db = datastore;
    var transaction = db.transaction(['videos'], 'readwrite');
    var objStore = transaction.objectStore('videos');

    var keyRange = IDBKeyRange.lowerBound(0);
    var cursorRequest = objStore.openCursor(keyRange);

    var videos = [];

    transaction.oncomplete = function(e) {
      // Execute the callback function.
      callback(Videos);
    };

    cursorRequest.onsuccess = function(e) {
      var result = e.target.result;
      
      if (!!result == false) {
        return;
      }
      
      videos.push(result.value);

      result.continue();
    };

    cursorRequest.onerror = vDb.onerror;
  };


  /**
   * Create a new todo item.
   * @param {string} text The todo item.
   */
  vDb.createVideos = function(text, callback) {
    // Get a reference to the db.
    var db = datastore;

    // Initiate a new transaction.
    var transaction = db.transaction(['videos'], 'readwrite');

    // Get the datastore.
    var objStore = transaction.objectStore('videos');
    
    // Create the datastore request.
    for (var i in json_data){
      var request = objStore.put(i);  
    }

    // Handle a successful datastore put.
    request.onsuccess = function(e) {
      // Execute the callback function.
      callback(todo);
    };

    // Handle errors.
    request.onerror = vDb.onerror;
  };


  /**
   * Delete a todo item.
   * @param {int} id The timestamp (id) of the todo item to be deleted.
   * @param {function} callback A callback function that will be executed if the 
   *                            delete is successful.
   */
  vDb.deleteTodo = function(id, callback) {
    var db = datastore;
    var transaction = db.transaction(['videos'], 'readwrite');
    var objStore = transaction.objectStore('videos');
    
    var request = objStore.delete(id);
    
    request.onsuccess = function(e) {
      callback();
    }
    
    request.onerror = function(e) {
      console.log(e);
    }
  };


  // Export the vDb object.
  return vDb;
}());
