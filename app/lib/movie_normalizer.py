import subprocess
import tempfile
import shutil
import os
import sys
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
            pan_filter = "pan=stereo|FL=0.9*FL+1.0*FC+0.75*LFE+0.25*BL+0.25*SL|FR=0.9*FR+1.0*FC+0.75*LFE+0.25*BR+0.25*SR"
        elif layout.startswith("7.1"):
            pan_filter = "pan=stereo|FL=0.85*FL+1.0*FC+0.75*LFE+0.35*BL+0.35*SL|FR=0.85*FR+1.0*FC+0.75*LFE+0.35*BR+0.35*SR"
        else:
            raise ValueError(f"Unsupported channel layout: {layout}")
        logger.info(f"Pan filter: \"{pan_filter}\"")
        return pan_filter

    def build_audio_filter(self, layout: str) -> str:
        """
        1. acompressor (The "Squasher")

        threshold=-22dB:ratio=4:attack=5:release=250:makeup=4:mix=0.9

        This is a compressor. It reduces the volume of loud sounds.

            threshold=-22dB: Any sound louder than -22dB triggers the compressor. This is a low threshold, meaning it catches almost everything except silence.

            ratio=4: For every 4dB the volume goes over the threshold, the compressor only allows it to rise by 1dB. This effectively "squashes" loud scenes.

            attack=5: 5ms reaction time. It clamps down on gunshots/explosions almost instantly.

            makeup=4: Adds 4dB of volume to the entire signal to make up for the volume lost by squashing the peaks.

            mix=0.9: This is "Parallel Compression." It mixes 90% of the compressed audio with 10% of the original. This prevents the audio from sounding too "flat" or robotic.

        2. dynaudnorm (The "Booster")

        f=125:g=13:p=0.85

        This is the Dynamic Audio Normalizer. While the compressor pushes loud noises down, this pulls quiet noises up.

            It looks at "windows" of audio (125ms long, defined by f=125) and dynamically raises the gain to hit a target peak (p=0.85).

            This is the specific filter that makes whispering audible without you turning up the volume.

        3. equalizer (The "Clarity")

        f=2000:t=q:w=1:g=2

        This is a specific EQ boost to help you understand what people are saying.

            f=2000: Targets 2000 Hz (2kHz). This is the frequency range where human consonant sounds (T, K, S, P) live. These sounds define intelligibility.

            g=2: Adds a +2dB boost to this range.

            Result: Voices sound crisper and "closer" to the listener.

        4. highpass (The "De-Rumbler")

        f=20

        This cuts off all frequencies below 20Hz. The hearable frequency range for humans is generally considered to be from 20 Hz to 20,000 Hz (20 kHz). 

            Why? In a downmix (Stereo), deep sub-bass (earthquake rumbles) eats up a lot of "headroom" (energy) but isn't very audible on standard TV speakers or headphones.

            Removing this invisible energy allows the rest of the audio to be louder and clearer without distortion.

        5. alimiter (The "Safety Net")

        limit=0.98

        This is a Lookahead Limiter.

            Because the previous filters (makeup=4 and dynaudnorm) are adding volume, there is a risk the audio could go above the digital maximum (0dB) and crackle.

            This filter sets a hard ceiling at 0.98. If the audio tries to go higher, it is smoothly limited to prevent digital clipping/distortion.

        Summary of the Flow

            Compressor: "Whoa, that explosion is too loud! Turn it down."

            DynAudNorm: "Hey, they are whispering now. Turn it up!"

            Equalizer: "Make the voices crisp so we can hear the words."

            HighPass: "Get rid of that deep mud/rumble we don't need."

            Limiter: "Don't let the volume go over the red line."
        """
        pan_filter = self.build_pan_filter(layout)
        filter_str = f"{pan_filter}," \
            "acompressor=threshold=-12dB:ratio=3:attack=5:release=250:makeup=1:mix=0.5," \
            "dynaudnorm=f=125:g=13:p=0.85," \
            "equalizer=f=2000:t=q:w=1:g=2," \
            "highpass=f=20," \
            "alimiter=limit=0.95"
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
                "-c:a", "libopus", "-b:a", "224k", "-vbr", "on", "-ac", "2",
                "-f", "matroska",
                "-hide_banner", "-nostats", "-loglevel", "error", "-progress", "pipe:1",
                audio_out
            ]
            try:
                logger.info(f"Running ffmpeg:\n```\n{' '.join(cmd)}\n```")
                # Capture stderr so we can log the ffmpeg error output if it fails.
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            except subprocess.CalledProcessError as e:
                if getattr(e, 'stderr', None):
                    logger.error("ffmpeg stderr:\n\n%s", e.stderr)
                logger.exception("ffmpeg raised CalledProcessError")
                sys.exit(1)
            except Exception as e:
                if getattr(e, 'stderr', None):
                    logger.error("ffmpeg stderr:\n\n%s", e.stderr)
                logger.exception("Unexpected error during ffmpeg processing")
                sys.exit(1)
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
        cmd.extend(["-c:a", "libopus", "-b:a", "224k", "-vbr", "on"])
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
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as e:
            logger.error("ffmpeg failed (returncode=%s cmd=%s)", e.returncode, e.cmd)
            if getattr(e, 'stderr', None):
                logger.error("ffmpeg stderr:\n%s", e.stderr)
            logger.exception("ffmpeg raised CalledProcessError during merge")
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
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as e:
            logger.error("mkvmerge failed (returncode=%s cmd=%s)", e.returncode, e.cmd)
            if getattr(e, 'stderr', None):
                logger.error("mkvmerge stderr:\n%s", e.stderr)
            logger.exception("mkvmerge raised CalledProcessError")
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
