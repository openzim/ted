#!/bin/sh

###
# download JS dependencies and place them in our templates/assets folder
# then launch our ogv.js script to fix dynamic loading links
###

if ! command -v curl > /dev/null; then
	echo "you need curl."
	exit 1
fi

if ! command -v unzip > /dev/null; then
	echo "you need unzip."
	exit 1
fi

# Absolute path this script is in.
SCRIPT_PATH="$( cd "$(dirname "$0")" ; pwd -P )"
ASSETS_PATH="${SCRIPT_PATH}/ted2zim/templates/assets"

echo "About to download JS assets to ${ASSETS_PATH}"

echo "getting video.js"
curl -L -O https://github.com/videojs/video.js/releases/download/v7.8.1/video-js-7.8.1.zip
rm -rf $ASSETS_PATH/videojs
mkdir -p $ASSETS_PATH/videojs
unzip -o -d $ASSETS_PATH/videojs video-js-7.8.1.zip
rm -rf $ASSETS_PATH/videojs/alt $ASSETS_PATH/videojs/examples
rm -f video-js-7.8.1.zip

echo "getting chosen.jquery.js"
curl -L -O https://github.com/harvesthq/chosen/releases/download/v1.8.7/chosen_v1.8.7.zip
rm -rf $ASSETS_PATH/chosen
mkdir -p $ASSETS_PATH/chosen
unzip -o -d $ASSETS_PATH/chosen chosen_v1.8.7.zip
rm -rf $ASSETS_PATH/chosen/docsupport $ASSETS_PATH/chosen/chosen.proto.* $ASSETS_PATH/chosen/*.html $ASSETS_PATH/chosen/*.md
rm -f chosen_v1.8.7.zip

echo "getting jquery.min.js"
curl -L -o $ASSETS_PATH/jquery.min.js https://code.jquery.com/jquery-3.5.1.min.js