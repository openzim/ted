# 2.0.8.dev0

- fixed bug in video URL finding if ted json as an h264 entry with None value

# 2.0.7

- use `eng` as default locale

# 2.0.6

- [multi] added retry over failure to get playlist slug
- use WebP images instead of JPEG for thumbnails and speaker images
- add multithreading support and ability to download videos hosted on youtube
- fixed usage on older browsers (without ES6 support)
- limited YoutubeDownloader threads to 1
- use slug instead of video ID to make urls meaningful
- fixed bug that required clicking the next page button twice
- add i18n support
- add translations for Hindi

# 2.0.5

- use pylibzim to create zim
- add variable "{slug}" in ted2zim-multi which will be replaced by the playlist/topic slug (with dashes) automatically
- fix layout on mobile devices

# 2.0.4

- ted2zim-multi forwards return-code from ted2zim process on failure
- Fixed clashing argument between `--name` and `--name-format` in ted2zim-multi

# 2.0.3

- added ted2zim-multi for multi zim creation
- added --tmp-dir to specify the path folder where the temporary build directory will be created
- `{period}` can be passed in `--zim-file` and be replaced with date as YYYY-MM

# 2.0.2

- now handling incorrect TED website responses with retries
- fixed crash on missing language details
- removed duplicated subtitles
- fixed auto-description when title is supplied
- removed --max-videos-per-topic option to decrease complexity
- refactoring of code

# 2.0.1

- fixed missing files in package
- Fixed docker recipe (zimwriterfs version)

# 2.0.0

- Rewritten the scraper in python3
- New command to run `ted2zim`
- Introduced changelog
- Topicwise scraping supported
- Support for playing webm files where not supported natively using videojs-ogvjs
- Web dependencies removed from repository
- New Dockerfile
- New project structure
- Added S3 based optimization cache support
- Add support for TED playlists
- Add support to filter videos available in a specific language based on audio and subtitles
- Add option to choose subtitle languages
