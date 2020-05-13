$.urlParam = function(name){
    var results = new RegExp('[?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results==null) {
       return null;
    }
    return decodeURI(results[1]) || 0;
}

window.onload = function() {
    requested_language = $.urlParam('lang')
    html_name = window.location.pathname.substring(window.location.pathname.lastIndexOf("/") + 1);
    video_id = html_name.substring(0, html_name.lastIndexOf("."));
    for (i in json_data) {
        if(json_data[i].id == video_id){
            var idx = 0;
            for (j in json_data[i].title) {
                if (json_data[i].title[j].lang == requested_language) {
                idx = j;
                }
            }
            document.getElementById("title-head").innerHTML = json_data[i].title[idx].text;
            document.getElementById("description-text").innerHTML = json_data[i].description[idx].text;
            document.getElementById("title-text").innerHTML = json_data[i].title[idx].text;
        }
    }
};