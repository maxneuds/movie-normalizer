"""movie-normalizer CLI

Usage: python app.py --input <input_file> --output <output_file>

This script probes the input media file for audio streams, creates
normalized stereo Opus renditions of each audio track, and merges them
back into the output container (MKV by default). The CLI exposes two
positional arguments: file_path_input and file_path_output. Use -h/--help
for more information.
"""

from argparse import ArgumentParser
from lib.movie_normalizer import MovieNormalizer
from lib.logger import logger


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Normalize audio tracks in a movie and write results to a new file")
    parser.add_argument("file_path_input", help="Path to the input media file (e.g. movie.mkv)")
    parser.add_argument("file_path_output", help="Path for the output media file (will be overwritten if exists)")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    normalizer = MovieNormalizer()

    file_path_input = args.file_path_input
    file_path_output = args.file_path_output

    logger.info(f"Starting normalization: input={file_path_input} output={file_path_output}")

    # Probe audio streams
    streams = normalizer.get_audio_streams(file_path_input)
    if not streams:
        logger.info("No audio streams found; nothing to do.")
        return

    # Create normalized temporary audio files
    normalized_audio = normalizer.normalize_audio_streams(file_path_input, streams)

    # Merge using mkvmerge if available, otherwise ffmpeg merge
    try:
        # Prefer mkvmerge method (keeps original streams intact)
        result = normalizer.merge_streams_mkv(file_path_input, file_path_output, normalized_audio)
    except Exception:
        # Fall back to ffmpeg merging
        result = normalizer.merge_streams_ffmpeg(file_path_input, file_path_output, normalized_audio)

    # Cleanup temp files
    normalizer.delete_temp_files(normalized_audio)

    logger.info(f"Finished: {result}")


if __name__ == "__main__":
    main()
