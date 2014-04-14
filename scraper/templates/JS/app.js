
window.onload = function() {
  window.indexedDB = window.indexedDB || window.mozIndexedDB || window.webkitIndexedDB || window.msIndexedDB;
  window.IDBTransaction = window.IDBTransaction || window.webkitIDBTransaction || window.msIDBTransaction;
  window.IDBKeyRange = window.IDBKeyRange || window.webkitIDBKeyRange || window.msIDBKeyRange;
  
  // Display the video items.
  videoDB.open(createDataStore);
  
  return false;
};

function createDataStore() {
  getDataCount(function(count){
    setupListener(count);
  });
  
  videoDB.createVideo(function(){
    refreshVideos();
  });
}

function getDataCount(callback){
  videoDB.fetchVideos(0, 0, function(count){
    callback(count.length);
  });
}

function setupListener(dbCount){
  var page = 1;
  var count =  Math.ceil(dbCount / 40);

console.log(count);
console.log(dbCount);

  var leftArrow = document.getElementsByClassName('left-arrow')[0];
  var rightArrow = document.getElementsByClassName('right-arrow')[0];
  var pageText = document.getElementsByClassName('pagination-text')[0];

  leftArrow.onclick = function() {
    if (page != 1){
      --page;
    }
    pageText.innerHTML = 'Page ' + page;
  };

  rightArrow.onclick = function() {
    if (page < count){
      ++page;  
    }
    pageText.innerHTML = 'Page ' + page;
  };
}

// Update the list of video items.
function refreshVideos() {  
  videoDB.fetchVideos(0, 20, function(videos) {
    var videoList = document.getElementById('video-items');
    videoList.innerHTML = '';
    
    for(i in videos) {
      // Read the video items backwards (most recent first).
      var video = videos[i];

      var li = document.createElement('li');
      var checkbox = document.createElement('input');
      checkbox.type = "checkbox";
      checkbox.className = "video-checkbox";
      checkbox.setAttribute("data-id", video.id);
      
      li.appendChild(checkbox);
      
      var span = document.createElement('span');
      span.innerHTML = video.title;
      
      li.appendChild(span);
      videoList.appendChild(li);
      
    }
  });
}
