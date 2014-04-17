
var videoDB = (function() {
  var ITEMS_PER_PAGE = 40;
  var db = {};
  var data;
  var page = 1;

  db.loadData = function(language, callback){
    if (typeof language === 'undefined'){
      data = json_data;
    }
    else {
      data = [];
      for (i in json_data){
        if (json_data[i].languages.indexOf(language) > -1) {
          data.push(json_data[i]);
        }
      }
    }
    if (typeof callback !== 'undefined') {
      callback();
    }
  }

  db.getData = function() {
    return data;
  }

  db.getPageCount = function() {
    return Math.floor(data.length / ITEMS_PER_PAGE);
  }

  db.pageForward = function(callback) {
    var change = false;
    if (page <=  db.getPageCount()) {
      page++;
      change = true;
    }
    callback(change);
  }
  
  db.pageBackwards = function(callback) {
    var change = false;
    if (page != 1) {
      page--;
      change = true;
    }
    callback(change);
  }

  db.resetPage = function() {
    page = 1;
  }

  db.getPageNumber = function() {
    return page;
  }

  db.getPage = function(page) {
    var pageStart = (page-1)*ITEMS_PER_PAGE;
    var pageEnd = page*ITEMS_PER_PAGE;
    return data.slice(pageStart, pageEnd);
  }

  return db;

}());
