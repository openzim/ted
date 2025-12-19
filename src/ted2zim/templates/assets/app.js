window.onload = function () {
  // Check if a language is stored using the storage utility
  let selectedLanguage = storage.getItem(SELECTED_LANGUAGE_KEY) || "en";

  // If a language is stored, select it in the dropdown
  // This ensures the dropdown reflects the stored language on page load.
  setupLanguageFilter();
  setupPagination();

  $('.chosen-select').val(selectedLanguage).trigger('chosen:updated');
  videoDB.resetPage();
  // Load the initial data. 
  // This will load the data_{lang}.js data
  videoDB.loadData(selectedLanguage, function () {
    var data = videoDB.getPage(videoDB.getPageNumber());
    refreshVideos(data);
    refreshPagination();
  });

};

/** 
 * Apply a language filter, that is selected by the
 * drop down options <select> menu. 
 * This will then only display items that have
 * subtitles in the selected language.
 */
function setupLanguageFilter() {
  $('.chosen-select').chosen({ width: "380px" }).change(function (_, params) {
    var language = params.selected;
    // Store the selected language using the storage utility
    storage.setItem(SELECTED_LANGUAGE_KEY, language);
    // Load the data for the selected language and 
    // generate the video list.
    videoDB.resetPage();
    videoDB.loadData(language, function () {
      var data = videoDB.getPage(videoDB.getPageNumber());
      refreshVideos(data);
      refreshPagination();
    });
  });
}

/**
* This function handles the pagination:
* Clicking the back and forward button.
*/
function setupPagination() {

  function handlePagination() {
    var data = videoDB.getPage(videoDB.getPageNumber());
    refreshVideos(undefined, data);
    refreshPagination();
    window.scrollTo(0, 0);
  }

  var leftArrow = document.getElementById('left-arrow');
  var rightArrow = document.getElementById('right-arrow');

  leftArrow.onclick = function () {
    videoDB.pageBackwards(function () {
      handlePagination();
    });
  }

  rightArrow.onclick = function () {
    videoDB.pageForward(function () {
      handlePagination();
    });
  }
}

/**
 * Reset the page text on the pagination widget, 
 * if a new language has been applied.
 */
function refreshPagination() {
  var pageCount = videoDB.getPageCount();
  var pageBox = document.getElementById('pagination');
  var leftArrow = document.getElementById('left-arrow');
  var rightArrow = document.getElementById('right-arrow');

  if (pageCount > 1) {
    var pageText = document.getElementById('pagination-text');
    var pageNumber = videoDB.getPageNumber();
    pageText.innerHTML = pageText.getAttribute('data-text') + ' ' + pageNumber + '/' + pageCount;

    if (videoDB.getPageNumber() == 1) {
      leftArrow.style.visibility = 'hidden';
      rightArrow.style.visibility = 'visible';
    } else if (pageNumber == pageCount) {
      leftArrow.style.visibility = 'visible';
      rightArrow.style.visibility = 'hidden';
    } else {
      leftArrow.style.visibility = 'visible';
      rightArrow.style.visibility = 'visible';
    }

    pageBox.style.visibility = 'visible';
  } else {
    pageBox.style.visibility = 'hidden';
    leftArrow.style.visibility = 'hidden';
    rightArrow.style.visibility = 'hidden';
  }
}

/**
 * Dynamically generate the video item out of 
 * the passed in {pageData} parameter.
 * @param {pageData} Video data for the current page.
 */
function refreshVideos(pageData) {
  let videoList = document.getElementById('video-items');
  videoList.innerHTML = '';
  for (const element of pageData) {
    let video = element;
    let li = document.createElement('li');

    let a = document.createElement('a');
    a.href = video.slug;
    a.className = 'nostyle';
    let img = document.createElement('img');
    img.src = 'videos/' + video.id + '/thumbnail.webp';

    let author = document.createElement('p');
    author.id = 'author';
    author.innerHTML = video.speaker;

    let title = document.createElement('p');
    title.id = 'title';
    title.innerHTML = video.title;

    a.appendChild(img);
    a.appendChild(author);
    a.appendChild(title);
    li.appendChild(a);
    videoList.appendChild(li);
  }
}

$(document).ready(function () {
  $(".backtotop").on("click", function () { $('html, body').animate({ scrollTop: 0 }, 'slow'); });
});
