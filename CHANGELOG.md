## Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (as of version 2.0.11).

## [Unreleased]

### Fixed

-  Restore functionality to resist temporary bad TED responses when parsing video pages (#209)

## [3.0.2] - 2024-06-24

### Changed

- Updgrade to zimscraperlib 3.4.0 (including **new webm encoder presets to migrate to VP9 instead of VP8**) (#204)

### Fixed

- Retry logic is still failing because req might be null when timeout occurs (#203)
- Typo in disable-metadata-checks arg in ted2zim-multi (#202)

## [3.0.1] - 2024-05-14

### Fixed

- Change log level from ERROR to WARNING for missing translations (#197)
- Fix HTTP retries to consider any HTTP failure, not only bad HTTP status code (#162)

## [3.0.0] - 2024-04-19

### Added

- New `--long-description` CLI argument to set the ZIM long description
- New `--disable-metadata-check` CLI argument to disable the metadata checks which are automated since zimscraperlib 3.x
- When `--languages` CLI arugment is not passed, no filtering by language is done (#171)

### Changed

- Changed default publisher metadata from 'Kiwix' to 'openZIM'
- Validate ZIM metadata as early as possible
- Migrate to zimscraperlib 3.3.2 (including **new VideoLowWebm encoder preset version 2**)
- Upgrade Python dependencies, including migration to Python 3.12

## Fixed

- Fix language metadata computation (#172)
- Fix computation of automatic description and long description
- Fix subtitles time offset (#177)
- Fix rare bug in display of videos title and description on video page
- Fix support for Youtube fallback when download video from TED CDN is not working (#164 + #182)
- Do not include videos which failed to be fetched / processed in the final list of videos on main page (#167, #169)
- Fix video not working on Safari iOS / iPad (#145)

## [2.1.0] - 2024-01-08

### Changed

- fixed search by topic to use new search API instead of broken web page scraping (#149)
- download_link is renamed request_url and can also perform POST requests (in addition to previous GET requests)
- upgrade to Python 3.11 from 3.8
- upgrade to zimscraperlib 2.1 + upgrade all other dependencies
- significant refactoring to adopt openZIM Python conventions
- activate stale bot + add convenient pull requests template

## [2.0.13] - 2023-04-24

### Changed

- download_link now retries all errors but 404
- Updated ogv.js to 1.8.9
- Fixed missing speaker photo (#144)

## [2.0.12] - 2022-10-03

### Changed

- Fixed crash on videos without speakers (#134)
- Adapted for no-namespace ZIM (#139)

## [2.0.11] - 2022-08-01

### Changed

- Fixed new video DOM change
- Fixed dependency issue (markupsafe)
- Don't fail on missing whoTheyAre
- Updated scraperlib (1.6.2) to fix mime guessing bug
- Removed inline JS to comply with some CSP (#128)

## [2.0.10]

- Special handling for playlist 57 (#127)
- ZIM entries now have Titles (#126)
- Updated for new playlists DOM (#124)
- Updated for new video DOM (#129)


## [2.0.9]

- updated scraperlib

## [2.0.8]

- fixed bug in video URL finding if ted json as an h264 entry with None value

## [2.0.7]

- use `eng` as default locale

## [2.0.6]

- [multi] added retry over failure to get playlist slug
- use WebP images instead of JPEG for thumbnails and speaker images
- add multithreading support and ability to download videos hosted on youtube
- fixed usage on older browsers (without ES6 support)
- limited YoutubeDownloader threads to 1
- use slug instead of video ID to make urls meaningful
- fixed bug that required clicking the next page button twice
- add i18n support
- add translations for Hindi

## [2.0.5]

- use pylibzim to create zim
- add variable "{slug}" in ted2zim-multi which will be replaced by the playlist/topic slug (with dashes) automatically
- fix layout on mobile devices

## [2.0.4]

- ted2zim-multi forwards return-code from ted2zim process on failure
- Fixed clashing argument between `--name` and `--name-format` in ted2zim-multi

## [2.0.3]

- added ted2zim-multi for multi zim creation
- added --tmp-dir to specify the path folder where the temporary build directory will be created
- `{period}` can be passed in `--zim-file` and be replaced with date as YYYY-MM

## [2.0.2]

- now handling incorrect TED website responses with retries
- fixed crash on missing language details
- removed duplicated subtitles
- fixed auto-description when title is supplied
- removed --max-videos-per-topic option to decrease complexity
- refactoring of code

## [2.0.1]

- fixed missing files in package
- Fixed docker recipe (zimwriterfs version)

## [2.0.0]

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
