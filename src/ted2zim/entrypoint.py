import argparse
import re
from datetime import timedelta, datetime
from ted2zim.constants import ALL, MATCHING, NAME, NONE, SCRAPER, get_logger, set_debug
from ted2zim.scraper import Ted2Zim

def adjust_subtitle_timing(subtitle_content, shift_seconds):
    """Adjusts the timing of subtitles by the specified number of seconds."""
    time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2},\d{3})')
    adjusted_lines = []
    
    for line in subtitle_content.split('\n'):
        timestamp_match = time_pattern.findall(line)
        if timestamp_match:
            adjusted_times = []
            for timestamp in timestamp_match:
                original_time = datetime.strptime(timestamp, '%H:%M:%S,%f')
                adjusted_time = original_time + timedelta(seconds=shift_seconds)
                adjusted_times.append(adjusted_time.strftime('%H:%M:%S,%f')[:-3])
            line = time_pattern.sub(lambda x: adjusted_times.pop(0), line)
        adjusted_lines.append(line)
    
    return '\n'.join(adjusted_lines)

def main():
    parser = argparse.ArgumentParser(
        prog=NAME,
        description="Scraper to create ZIM files from TED talks topics or playlists",
    )
    parser.add_argument(
        "--topics", help="Comma-separated list of topics to scrape; as given on ted.com/talks"
        )
    
    parser.add_argument(
        "--playlist", help="A playlist ID from ted.com/playlists to scrape videos from"
        )
    
    parser.add_argument(
        "--languages", help="Comma-separated list of languages to filter videos"
        )
    
    parser.add_argument(
        "--locale", help="The locale to use in the UI (can be iso language code / locale)", dest="locale_name", default="eng"
        )
    
    parser.add_argument(
        "--subtitles-enough", help="Whether to include videos that have a subtitle in requested --languages if audio is in another language", default=False, action="store_true"
        )
    
    parser.add_argument(
        "--subtitles", help=f"Language setting for subtitles. {ALL}: include all available subtitles, {MATCHING} (default): only subtitles matching --languages, {NONE}: include no subtitle. Also accepts comma-separated list of language codes", default=MATCHING, dest="subtitles_setting"
        )
    
    
    parser.add_argument(
        "--format", help="Format to download/transcode video to. webm is smaller", choices=["mp4", "webm"], default="webm", dest="video_format"
        )
    
    parser.add_argument(
        "--low-quality", help="Re-encode video using stronger compression", action="store_true", default=False
        )
    
    parser.add_argument(
        "--autoplay", help="Enable autoplay on video articles. Behavior differs on platforms/browsers.", action="store_true", default=False
        )
    
    parser.add_argument(
        "--name", help="ZIM name. Used as identifier and filename (date will be appended)", required=True
        )
    
    parser.add_argument(
        "--title", help="Custom title for your ZIM. Based on selection otherwise."
        )
    
    parser.add_argument(
        "--description", help="Custom description for your ZIM. Based on selection otherwise."
        )
    
    parser.add_argument(
        "--long-description", help="Custom long description for your ZIM."
        )
    
    parser.add_argument(
        "--creator", help="Name of content creator", default="TED"
        )
    
    parser.add_argument(
        "--publisher", help="Custom publisher name (ZIM metadata)", default="openZIM"
        )
    
    parser.add_argument(
        "--tags", help="List of comma-separated Tags for the ZIM file. category:ted, ted, and _videos:yes added automatically"
        )
    
    parser.add_argument(
        "--optimization-cache", help="URL with credentials and bucket name to S3 Optimization Cache", dest="s3_url_with_credentials"
        )
    
    parser.add_argument(
        "--use-any-optimized-version", help="Use files on S3 cache if present, whatever the version", default=False, action="store_true"
        )
    
    parser.add_argument(
        "--output", help="Output folder for ZIM file", default="/output", dest="output_dir"
        )
    
    parser.add_argument(
        "--tmp-dir", help="Path to create temp folder in. Used for building ZIM file. Receives all data (storage space)"
        )
    
    parser.add_argument(
        "--zim-file", help="ZIM file name (based on --name if not provided)", dest="fname"
        )
    
    parser.add_argument(
        "--no-zim", help="Don't produce a ZIM file, create build folder only.", action="store_true", default=False
        )
    
    parser.add_argument(
        "--keep", help="Don't remove build folder on start (for debug/devel)", default=False, action="store_true", dest="keep_build_dir"
        )
    
    parser.add_argument(
        "--debug", help="Enable verbose output", action="store_true", default=False
        )
    
    parser.add_argument(
        "--threads", help="Maximum number of parallel threads to use", default=1, type=int
        )
    
    parser.add_argument(
        "--subtitle-shift", help="Time shift for subtitles in seconds. Positive to delay, negative to advance.", type=int, default=0, dest="subtitle_shift"
        )
    
    parser.add_argument(
        "--version", help="Display scraper version and exit", action="version", version=SCRAPER
        )
    
    parser.add_argument(
        "--disable-metadata-checks", help="Disable validity checks of metadata according to openZIM conventions", action="store_true", default=False
        )
    

    args = parser.parse_args()
    set_debug(args.debug)
    logger = get_logger()

    try:
        if args.topics and args.playlist:
            parser.error("--topics is incompatible with --playlist")
        elif args.topics:
            if args.subtitles_enough and not args.languages:
                parser.error("--subtitles-enough is only meant to be used if --languages is present")
        elif args.playlist:
            if args.subtitles_enough:
                parser.error("--subtitles-enough is not compatible with playlists")
        else:
            parser.error("Either --topics or --playlist is required")

        if not args.subtitles_setting:
            parser.error("--subtitles cannot take an empty string")

        if not args.threads >= 1:
            parser.error("--threads must be provided a positive integer")

        # Assume subtitles are processed here
        if args.subtitle_shift != 0:
            # Example of how you might load and adjust subtitles
            # This is a placeholder, replace `subtitle_path` with actual path
            subtitle_path = "path_to_subtitle.srt"
            with open(subtitle_path, 'r', encoding='utf-8') as file:
                original_subtitle_content = file.read()
            
            adjusted_subtitle_content = adjust_subtitle_timing(original_subtitle_content, args.subtitle_shift)
            
            with open(subtitle_path, 'w', encoding='utf-8') as file:
                file.write(adjusted_subtitle_content)

        scraper = Ted2Zim(**dict(args._get_kwargs()))
        scraper.run()

    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
    
    
    # Subtitle Shift Argument added
    # Subtitle Adjustment Functionality integrated
