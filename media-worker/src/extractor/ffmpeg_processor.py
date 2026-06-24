import logging
import os
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("media-worker")


class FFmpegProcessor:
    @staticmethod
    def extract_audio(video_path: str, audio_path: str) -> str:
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-q:a', '0',
            '-map', 'a',
            '-ac', '1',
            '-acodec', 'libmp3lame',
            audio_path
        ]

        logger.info(f"[FFmpeg] Extracting audio: {' '.join(cmd)}")
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        return os.path.abspath(audio_path)

    @staticmethod
    def extract_keyframes(video_path: str, output_dir: str, use_scene_detection: bool = False) -> list[str]:
        os.makedirs(output_dir, exist_ok=True)

        if use_scene_detection:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', "select='gt(scene,0.3)',showinfo",
                '-vsync', 'vfr',
                '-q:v', '2',
                os.path.join(output_dir, 'frame_%03d.jpg')
            ]
        else:
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', 'fps=1/3',
                '-q:v', '2',
                os.path.join(output_dir, 'frame_%03d.jpg')
            ]

        logger.info(f"[FFmpeg] Extracting keyframes: {' '.join(cmd)}")
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        frames = [
            os.path.abspath(os.path.join(output_dir, f))
            for f in os.listdir(output_dir)
            if f.startswith('frame_') and f.endswith('.jpg')
        ]

        if not frames:
            raise RuntimeError("FFmpeg produced no keyframes")

        return sorted(frames)

    @staticmethod
    def extract_all(video_path: str, audio_path: str, frames_dir: str, use_scene_detection: bool = False) -> tuple[str, list[str]]:
        """Extract audio and keyframes in parallel. Returns (audio_path, keyframe_paths)."""
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="ffmpeg") as pool:
            audio_future = pool.submit(FFmpegProcessor.extract_audio, video_path, audio_path)
            frames_future = pool.submit(FFmpegProcessor.extract_keyframes, video_path, frames_dir, use_scene_detection)

            audio_result = audio_future.result()
            frames_result = frames_future.result()

        logger.info(f"[FFmpeg] Parallel extraction complete: audio + {len(frames_result)} frames")
        return audio_result, frames_result
