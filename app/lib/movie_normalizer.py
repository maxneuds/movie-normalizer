import subprocess
import tempfile
import shutil
import os
from lib.logger import logger
from typing import List, Tuple
from pathlib import Path


class MovieNormalizer:
    def __init__(self):
        pass

    def get_audio_streams(self, file_path_input: str) -> List[Tuple]:
        """
        Returns a list of tuples: (track_position, language, channel_layout)
        track_position is 0-based audio track index for FFmpeg mapping
        """
        logger.info(f"Probing audio streams for file: {file_path_input}")
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=channel_layout:stream_tags=language",
            "-of", "csv=p=0", file_path_input
        ]
        output = subprocess.check_output(cmd, text=True)
        streams = []
        for i, line in enumerate(output.strip().splitlines()):
            parts = line.strip().split(',')
            layout = parts[0] if len(parts) > 0 and parts[0] else "stereo"
            lang = parts[1] if len(parts) > 1 and parts[1] else "und"
            streams.append((i, lang, layout))
        return streams

    def build_pan_filter(self, layout):
        """
        Returns a pan filter string based on the channel layout.
        """
        logger.info(f"Set pan filter for layout: {layout}")
        if layout.startswith("5.1"):
            pan_filter = "pan=stereo|FL=0.9*FL+1.1*FC+0.75*LFE+0.25*BL+0.25*SL|FR=0.9*FR+1.1*FC+0.75*LFE+0.25*BR+0.25*SR"
        elif layout.startswith("7.1"):
            pan_filter = "pan=stereo|FL=0.85*FL+1.0*FC+0.75*LFE+0.2*BL+0.2*SL+0.15*BL2+0.15*BR2|FR=0.85*FR+1.0*FC+0.75*LFE+0.2*BR+0.2*SR+0.15*BL2+0.15*BR2"
        else:
            raise ValueError(f"Unsupported channel layout: {layout}")
        logger.info(f"Pan filter: \"{pan_filter}\"")
        return pan_filter

    def build_audio_filter(self, layout: str) -> str:
        """
        Acompressor parameters:
        This is a dynamic range compressor — it reduces the difference between quiet and loud sounds.
        threshold=-22dB
        Compression starts when the signal exceeds –22 dBFS. Everything quieter passes untouched.
        ratio=4
        Once over the threshold, volume increases are reduced — e.g. a +3.5 dB input increase only becomes +1 dB output.
        attack=5
        Reacts within 10 ms to loud peaks — fast enough to catch sudden shouts or gunshots.
        release=250
        Returns to normal gain over 250 ms after the signal drops — keeps it natural instead of pumping.
        makeup=4
        Adds 4 dB of gain afterward to make up for the reduction, so overall loudness stays consistent.
        mix=0.9
        90% compressed + 10% dry signal — this “parallel compression” keeps transients (like sibilants and detail) alive.
        Dynaudnorm parameters:
        This is dynamic audio normalization, a kind of “smart loudness leveling.”
        f=125
        Frame size in milliseconds. Smaller = more reactive.
        (We reduced it to an odd value because the filter requires that — 13, 125, 201, etc.)
        g=13
        Max gain in dB. It won’t boost quiet sections by more than +13 dB.
        p=0.85
        Peak-to-average ratio; closer to 1.0 means more aggressive leveling.
        0.85 keeps it natural but prevents big dips in dialogue.
        Equalizer parameters:
        f=2000 → Center frequency = 2 kHz, the core of human speech clarity
        t=q → “Q” filter type = peaking around the target frequency
        w=1 → Bandwidth (fairly wide)
        g=2 → +2 dB boost
        Highpass parameters:
        f=40 → Cutoff frequency = 40 Hz to remove inaudible sub-bass rumble
        Alimiter parameters:
        limit=0.98 → Prevents clipping by ensuring the audio never exceeds 98% of full scale
        """
        pan_filter = self.build_pan_filter(layout)
        filter_str = f"{pan_filter}," \
            "acompressor=threshold=-22dB:ratio=4:attack=5:release=250:makeup=4:mix=0.9," \
            "dynaudnorm=f=125:g=13:p=0.85," \
            "equalizer=f=2000:t=q:w=1:g=2," \
            "highpass=f=40," \
            "alimiter=limit=0.98"
        return filter_str

    def normalize_audio_streams(self, file_path_input: str, streams: List[Tuple]) -> str:
        results = []
        for stream in streams:
            track_pos, lang, layout = stream
            audio_filter = self.build_audio_filter(layout)
            logger.info(f"FFMPEG: Create normalized stereo audio stream from track {track_pos}: {lang} {layout}")
            audio_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mka").name
            cmd = [
                "ffmpeg", "-y", "-i", file_path_input,
                "-map", f"0:a:{track_pos}",
                "-af", audio_filter,
                "-c:a", "libopus", "-b:a", "192k", "-vbr", "on", "-ac", "2",
                "-f", "matroska",
                "-hide_banner", "-nostats", "-loglevel", "error", "-progress", "pipe:1",
                audio_out
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError as e:
                logger.error("ffmpeg failed:", e.returncode, e.cmd)
                logger.error("stderr:", e.stderr)
            logger.info(f"Created audio file: {audio_out} (lang={lang})")
            results.append((audio_out, lang, layout))
        return results

    def merge_streams_ffmpeg(self, file_path_input: str, file_path_output: str, audio_streams: List[Tuple]) -> str:
        # Start FFMPEG merge command with input file and set overwrite target
        cmd = ["ffmpeg", "-y", "-i", file_path_input]
        # Add new audio streams as additional inputs
        for audio_file, _, _ in audio_streams:
            cmd.extend(["-i", audio_file])
        # Map video and subtitles
        # -map 0:v : Keep all video streams from original
        # -map 0:s? : Keep all subtitle streams from original if they exist
        # -map 0:a : Keep all original audio streams
        cmd.extend(["-map", "0:v", "-map", "0:s?", "-map", "0:a"])
        # Add old and new audio streams
        for i in range(len(audio_streams)):
            cmd.extend(["-map", f"{i+1}:a"])
        # Copy everything by default
        cmd.extend(["-c:v", "copy", "-c:s", "copy"])
        # Re-encode new audio stream into mkv-compatible opus
        cmd.extend(["-c:a", "libopus", "-b:a", "192k", "-vbr", "on"])
        # Set new audio stream names (metadata)
        for i, (_, lang, layout) in enumerate(audio_streams):
            n = i+len(audio_streams)
            filter_metadata = f"-metadata:s:a:{n}"
            cmd.extend([
                filter_metadata,
                f"title={lang.upper()} stereo-max",
                filter_metadata,
                f"language={lang}",
                f"-disposition:a:{n}", "0",  # Disable any default flag on new audio streams
            ])
        # Set log level
        cmd.extend(["-hide_banner", "-nostats", "-loglevel", "error", "-progress", "pipe:1"])
        # Set output file
        cmd.append(file_path_output)
        logger.info(f"Merging new audio stream into file: {file_path_output}")
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            logger.error("ffmpeg failed:", e.returncode, e.cmd)
            logger.error("stderr:", e.stderr)
        logger.info(f"Result: {file_path_output}")
        return file_path_output

    def merge_streams_mkv(self, file_path_input: str, file_path_output: str, audio_streams: List[Tuple]) -> str:
        # Start mkvmerge command
        cmd = ["mkvmerge", "-o", file_path_output, file_path_input]
        # Add new audio streams
        for i, (audio_file, lang, layout) in enumerate(audio_streams):
            cmd.extend([
                "--language", f"0:{lang}",
                "--track-name", f"0:\"{lang.upper()} stereo-max\"",
                "--default-track", f"0:no",
                audio_file
            ])
        logger.info(f"Merging new audio stream into file: {file_path_output}")
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            logger.error("mkvmerge failed:", e.returncode, e.cmd)
            logger.error("stderr:", e.stderr)
        logger.info(f"Result: {file_path_output}")
        return file_path_output

    def delete_temp_files(self, audio_streams: List[Tuple]):
        for audio_file, _, _ in audio_streams:
            try:
                os.remove(audio_file)
                logger.info(f"Deleted temporary audio file: {audio_file}")
            except OSError as e:
                logger.error(f"Error deleting temporary file {audio_file}: {e.strerror}")

    def _debug_copy_audio_files(self, audio_files: List[Tuple[str, str]], debug_dir: str):
        debug_path = Path(debug_dir)
        debug_path.mkdir(parents=True, exist_ok=True)
        for audio_file, lang in audio_files:
            dest_file = debug_path / f"normalized_{Path(audio_file).name}_lang_{lang}.opus"
            shutil.copy(audio_file, dest_file)
            logger.info(f"Copied debug audio file to: {dest_file}")
