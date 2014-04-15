
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
      store.createIndex('languages', 'languages', { unique: false, multiEntry:true });
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
   * @param {lower} lower boundry for the database
   * @param {upper} upper boundry for the database
   * @param {function} callback A function that will be executed once the items
   *        have been retrieved. Will be passed a param with
   *        an array of the video items.
   */
  vDB.fetchVideos = function(lower, upper, language, callback) {
    var db = datastore;
    var transaction = db.transaction(['videos'], 'readwrite');
    var objStore = transaction.objectStore('videos');
    var videos = [];

    var i = 0;

    if (language != 0) {
      var index = objStore.index("languages");
      var keyRange = IDBKeyRange.only(language);
      
      index.openCursor(keyRange).onsuccess = function(e) {
        var result = e.target.result;

        if (result) {
          if (i > lower && i < upper){
            videos.push(result.value); 
          }
           result.continue(); 
          i++;
        }
      };
    }
    else {
      if (lower == 0 && upper == 0) {
        var keyRange = IDBKeyRange.lowerBound(0);  
      }
      else {
        var keyRange = IDBKeyRange.bound(lower, upper);  
      } 

      objStore.openCursor(keyRange).onsuccess = function(e) {
        var result = e.target.result;
        
        if (result) {
          videos.push(result.value);
          result.continue(); 
        }
      };
    }
    
    transaction.oncomplete = function(e) {
      // Execute the callback function.
      callback(videos);
    };
  };


  /**
   * Create a new video item.
   * @param {callback} Callback, that'll be executed after 
   *        the Videos are created.
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

  // Return the vDB object.
  return vDB;
}());
