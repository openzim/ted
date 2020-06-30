# 2.0.4.dev0

- ted2zim-multi now returns correct return codes
- argument abbreviations not allowed in ted2zim-multi to prevent --name being read as --name-format

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
