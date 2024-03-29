from zimscraperlib.video.encoding import reencode

from ted2zim.constants import get_logger

logger = get_logger()


def post_process_video(video_dir, video_id, preset, video_format, low_quality):
    """apply custom post-processing to downloaded video

    - resize thumbnail
    - recompress video if incorrect video_format or low_quality requested
    """

    # find downloaded video from video_dir
    files = [
        p for p in video_dir.iterdir() if p.stem == "video" and p.suffix != ".webp"
    ]
    if len(files) == 0:
        logger.error(f"Video file missing in {video_dir} for {video_id}")
        logger.debug(list(video_dir.iterdir()))
        raise FileNotFoundError(f"Missing video file in {video_dir}")
    if len(files) > 1:
        logger.warning(
            f"Multiple video file candidates for {video_id} in {video_dir}. Picking "
            f"{files[0]} out of {files}"
        )
    src_path = files[0]

    # don't reencode if not requesting low-quality and received wanted format
    if not low_quality and src_path.suffix[1:] == video_format:
        return

    dst_path = src_path.parent.joinpath(f"video.{video_format}")
    logger.debug(f"Converting video {video_id}")
    success, process = reencode(
        src_path,
        dst_path,
        preset.to_ffmpeg_args(),
        delete_src=True,
        with_process=True,
        failsafe=True,
    )  # pyright: ignore[reportGeneralTypeIssues]
    if not success:
        if process:
            logger.error(process.stdout)
        raise Exception(f"Exception while re-encoding {src_path} for {video_id}")
