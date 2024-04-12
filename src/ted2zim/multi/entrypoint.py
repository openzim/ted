import argparse
import logging
import re

from ted2zim.constants import NAME, SCRAPER, get_logger, set_debug
from ted2zim.utils import has_argument

def adjust_subtitle_timing(subtitle_path, shift_seconds):
    """Adjusts the timing of subtitles by shift_seconds."""
    time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}),(\d{3})')
    output_lines = []
    with open(subtitle_path, 'r', encoding='utf-8') as file:
        for line in file:
            match = time_pattern.findall(line)
            if match:
                start_time, start_ms = map(int, match[0])
                end_time, end_ms = map(int, match[1])
                start = adjust_time(start_time, start_ms, shift_seconds)
                end = adjust_time(end_time, end_ms, shift_seconds)
                line = time_pattern.sub(f"{start} --> {end}", line)
            output_lines.append(line)
    
    with open(subtitle_path, 'w', encoding='utf-8') as file:
        file.writelines(output_lines)

def adjust_time(time_str, milliseconds, shift):
    """Adjust a time string by shift seconds."""
    hours, minutes, seconds = map(int, time_str.split(':'))
    total_seconds = hours * 3600 + minutes * 60 + seconds + shift
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

# In the above functions, subtitle synchronisation capabilities are integrated
# this accepts an integer representing a number of seconds to shift subtitle timings, (+ve for delay, and -ve for advancing)
  

def main():
    parser = argparse.ArgumentParser(
        prog=f"{NAME}-multi",
        description="Scraper to create ZIM file(s) from TED topic(s) or playlist(s)",
        epilog="All titles, descriptions and names can use the variables {identity} to "
        "get playlist ID or topic name (with dashes) in each case, or {slug} to get "
        "the slug (with dashes)",
        allow_abbrev=False,
    )

    parser.add_argument("--topics", help="Comma separated list of topics to scrape. Should be same as on ted.com/talks. Pass all to scrape all")
    parser.add_argument("--playlists", help="Comma separated list of playlist IDs to scrape. Pass all to scrape all")
    parser.add_argument("--indiv-zims", help="Make individual ZIMs for topics. Multiple ZIMs are always created for multiple playlists", action="store_true", dest="indiv_zims")
    parser.add_argument("--name-format", help="Format for building individual --name argument. Required in individual ZIMs mode.")
    parser.add_argument("--zim-file-format", help="Format for building individual --zim-file argument. Uses --name-format otherwise")
    parser.add_argument("--title-format", help="Custom title format for individual ZIMs")
    parser.add_argument("--description-format", help="Custom description format for individual ZIMs")
    parser.add_argument("--metadata-from", help="File path or URL to a JSON file holding custom metadata for individual playlists/topics. Format in README")
    parser.add_argument("--subtitle-shift", help="Time shift for subtitles in seconds, can be negative or positive", type=int, default=0)
    parser.add_argument("--debug", help="Enable verbose output", action="store_true", default=False)
    parser.add_argument("--version", help="Display scraper version and exit", action="version", version=SCRAPER)
    parser.add_argument("--disable-metadata-checks", help="Disable validity checks of metadata according to openZIM conventions", action="store_true", default=False)

    args, extra_args = parser.parse_known_args()

    if not args.playlists and not args.topics and not has_argument("playlist", extra_args):
        parser.error("Please provide topic(s) and/or playlist(s) to scrape")

    for arg in ("name", "title", "description", "zim-file"):
        if args.indiv_zims and has_argument(arg, extra_args):
            parser.error(f"Can't use --{arg} in individual ZIMs mode. Use --{arg}-format to set format.")

    if args.indiv_zims and not args.name_format:
        parser.error("--name-format is mandatory in individual ZIMs mode")

    set_debug(args.debug)
    logger = get_logger()
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    from ted2zim.multi.scraper import TedHandler

    try:
        handler = TedHandler(dict(args._get_kwargs()), extra_args=extra_args)
        if args.subtitle_shift != 0:
            # You would need to integrate the subtitle path and adjust the timing here.
            # This is just a placeholder as the actual implementation will depend on your application's structure.
            adjust_subtitle_timing("path_to_subtitle_file.srt", args.subtitle_shift)
        raise SystemExit(handler.run())
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
