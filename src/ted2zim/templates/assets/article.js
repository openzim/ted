$.urlParam = function(name){
    var results = new RegExp('[?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results==null) {
       return null;
    }
    return decodeURI(results[1]) || 0;
};

// Function to retrieve the selected language
function getSelectedLanguage() {
    return storage.getItem(SELECTED_LANGUAGE_KEY) || $.urlParam('lang');
}

window.onload = function() {
    var lang = getSelectedLanguage();
    if (lang && lang !== "undefined") {
        document.getElementById("title-head").innerHTML = $("p.title.lang-" + lang).text();
        $(".lang-default").css("display", "none");
        $(".lang-" + lang).css("display", "block");

        // Retrieve the value of the data-audio-lang attribute from the #video-wrapper element
        const audioLang = $('#video-wrapper').attr('data-audio-lang');

        if(audioLang != lang) {
            // Enable the subtitles for the selected language
            videojs("ted-video").ready(function () {
                const player = this;
                player.ready(() => {
                    const textTracks = player.textTracks();
                    Array.from(textTracks).some(t => {
                        // If the track's language matches the selected language, show it
                        if (t.language === lang) {
                            t.mode = 'showing';
                            return true;
                        }
                        return false;
                    });
                });
            });
        }
    }
};

$(document).ready(function() {
    $("#backtolist").on("click", function() { history.go(-1) });
});

