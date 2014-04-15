
// Define constants
var ITEMS_PER_PAGE = 40;

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
    refreshVideos(0, ITEMS_PER_PAGE);
  });
}

function getDataCount(callback){
  videoDB.fetchVideos(0, 0, 0, function(count){
    callback(count.length);
  });
}

function setupListener(dbCount){
  var page = 1;
  var count =  Math.floor(dbCount / 40);

  var leftArrow = document.getElementsByClassName('left-arrow')[0];
  var rightArrow = document.getElementsByClassName('right-arrow')[0];
  var pageText = document.getElementsByClassName('pagination-text')[0];

  leftArrow.onclick = function() {
    if (page != 1){
      --page;
      
      pageText.innerHTML = 'Page ' + page;
      var pageStart = (page-1)*ITEMS_PER_PAGE+1;
      var pageEnd = (page*ITEMS_PER_PAGE);
      // console.log('start ' + pageStart + ' end' + pageEnd);
      refreshVideos(pageStart, pageEnd);
    }
  };

  rightArrow.onclick = function() {
    if (page < count){
      ++page;  
      
      pageText.innerHTML = 'Page ' + page;
      var pageStart = page*ITEMS_PER_PAGE;
      var pageEnd = ((page+1)*ITEMS_PER_PAGE)-1;
      refreshVideos(pageStart, pageEnd);
    }
  };
}

/**
 * Update the grid of video items.
 * @param {lower} lower boundry for the database
 * @param {upper} upper boundry for the database
 */
function refreshVideos(upper, lower) {  
  videoDB.fetchVideos(upper, lower, 'en', function(videos) {
    var videoList = document.getElementById('video-items');
    videoList.innerHTML = '';
    
    for(i in videos) {
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
