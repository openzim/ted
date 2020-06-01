# dev

- fixed auto-description when title is supplied
- remove --max-videos-per-topic option to decrease complexity

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
