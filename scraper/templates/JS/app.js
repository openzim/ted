
window.onload = function() {
  setupLanguageFilter();
  setupPagination();
  videoDB.loadData(undefined, function() {
    var data = videoDB.getPage(videoDB.getPageNumber());
    refreshVideos(data);
  });

  return false;
};

function setupLanguageFilter() {
  $('.chosen-select').chosen().change(function(){
    resetPaginationText();
    language = arguments[1].selected;
    if (language == 'lang-all') {
      language = undefined;
    }
    videoDB.loadData(language, function() {
      var data = videoDB.getPage(videoDB.getPageNumber());
      refreshVideos(data);
    });    
  });
}

function setupPagination(){
  var leftArrow = document.getElementsByClassName('left-arrow')[0];
  var rightArrow = document.getElementsByClassName('right-arrow')[0];
  var pageText = document.getElementsByClassName('pagination-text')[0];

  leftArrow.onclick = function() {
    var shouldChange;
    videoDB.pageBackwards(function(change){
      shouldChange = change;
    });
    handlePagination(shouldChange);
  }

  rightArrow.onclick = function() {
    var shouldChange; 
    videoDB.pageForward(function(change){
      shouldChange = change;
    });
    handlePagination(shouldChange);
  }

  function handlePagination(shouldChange){
    if (shouldChange) {
      var data = videoDB.getPage(videoDB.getPageNumber());
      refreshVideos(data);
      pageText.innerHTML = 'Page ' + videoDB.getPageNumber();
      window.scrollTo(0, 0);
    }
  }
}

function resetPaginationText() {
  var pageText = document.getElementsByClassName('pagination-text')[0];
  videoDB.resetPage();
  pageText.innerHTML = 'Page ' + videoDB.getPageNumber();
}

function refreshVideos(pageData) {  
    var videoList = document.getElementById('video-items');
    videoList.innerHTML = '';
    
    for (i in pageData) {
      var video = pageData[i];
      var li = document.createElement('li');
      
      var a = document.createElement('a')
      a.href =  video['id']+'/index.html';
      a.style = 'nosytyle'

      var img = document.createElement('img');
      img.src = video['id']+'/thumbnail.jpg'; 

      var author = document.createElement('p');
      author.id = 'author';
      author.innerHTML = video['speaker'];
      
      var title = document.createElement('p');
      title.id = 'title';
      title.innerHTML = video['title'];

      a.appendChild(img);
      a.appendChild(author);
      a.appendChild(title);
      li.appendChild(a);

      videoList.appendChild(li);
    }
}
