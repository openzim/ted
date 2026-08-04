$.urlParam = function(name){
    var results = new RegExp('[?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results==null) {
       return null;
    }
    return decodeURI(results[1]) || 0;
};

// Function to retrieve the selected language
function getSelectedLanguage() {
    const stored = storage.getItem(SELECTED_LANGUAGE_KEY);

    if (stored && stored !== "undefined") {
        return stored;
    }
    const legacy = $.urlParam('lang');
    if (legacy && storage.getItem(SELECTED_LANGUAGE_KEY)) {
        storage.setItem(SELECTED_LANGUAGE_KEY, legacy);
        return legacy;
    }


    //fallback to en
    return "en";
}

window.onload = function() {
    var lang = getSelectedLanguage();
    if (lang && lang !== "undefined") {
        var langTitle = $("p.title.lang-" + lang);
        // Only switch to the selected language's title/description if this
        // specific talk actually has one (e.g. it was fetched as an audio
        // language) ; a talk can have many more subtitle languages than
        // title/description translations, so keep showing the default
        // language instead of hiding everything when there's no match.
        if (langTitle.length) {
            document.getElementById("title-head").innerHTML = langTitle.text();
            $(".lang-default").css("display", "none");
            $(".lang-" + lang).css("display", "block");
        }

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

$(document).ready(function () {
    $("#backtolist").on("click", function () { history.go(-1) });
});
