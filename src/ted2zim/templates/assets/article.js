$.urlParam = function(name){
    var results = new RegExp('[?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results==null) {
       return null;
    }
    return decodeURI(results[1]) || 0;
};

window.onload = function() {
    var lang = $.urlParam('lang');
    if (lang && lang !== "undefined") {
        document.getElementById("title-head").innerHTML = $("p.title.lang-" + lang).text();
        $(".lang-default").css("display", "none");
        $(".lang-" + lang).css("display", "block");
    }
};

$(document).ready(function() {
    $("#backtolist").on("click", function() { history.go(-1) });
});
