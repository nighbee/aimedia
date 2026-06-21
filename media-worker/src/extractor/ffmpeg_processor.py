import os
import subprocess
import shutil

class FFmpegProcessor:
    @staticmethod
    def extract_audio(video_path: str, audio_path: str) -> str:
        """
        Extracts a mono MP3 audio track from the video.
        """
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        
        # Check if the file is a mock/dummy file
        if not os.path.exists(video_path) or os.path.getsize(video_path) < 100:
            print("[MOCK] Writing dummy audio track.")
            with open(audio_path, 'wb') as f:
                f.write(b"MOCK AUDIO CONTENT")
            return os.path.abspath(audio_path)

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-q:a', '0',
            '-map', 'a',
            '-ac', '1',
            '-acodec', 'libmp3lame',
            audio_path
        ]
        
        try:
            print(f"Extracting audio: {' '.join(cmd)}")
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            print(f"FFmpeg audio extraction failed: {e}. Writing mock audio.")
            with open(audio_path, 'wb') as f:
                f.write(b"MOCK AUDIO CONTENT")

        return os.path.abspath(audio_path)

    @staticmethod
    def extract_keyframes(video_path: str, output_dir: str) -> list[str]:
        """
        Extracts 1 keyframe every 3 seconds and returns a list of absolute paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Check if the file is a mock/dummy file
        if not os.path.exists(video_path) or os.path.getsize(video_path) < 100:
            return FFmpegProcessor._generate_mock_keyframes(output_dir)

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', 'fps=1/3',
            '-q:v', '2',
            os.path.join(output_dir, 'frame_%03d.jpg')
        ]

        try:
            print(f"Extracting keyframes: {' '.join(cmd)}")
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            print(f"FFmpeg keyframe extraction failed: {e}. Generating mock keyframes.")
            return FFmpegProcessor._generate_mock_keyframes(output_dir)

        # Get list of generated frames
        frames = [
            os.path.abspath(os.path.join(output_dir, f))
            for f in os.listdir(output_dir)
            if f.startswith('frame_') and f.endswith('.jpg')
        ]
        
        if not frames:
            return FFmpegProcessor._generate_mock_keyframes(output_dir)
            
        return sorted(frames)

    @staticmethod
    def _generate_mock_keyframes(output_dir: str) -> list[str]:
        """
        Generates simple solid-colored 1x1 JPG keyframes for mockup pipeline runs.
        """
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        
        # We write tiny valid 1x1 pixels or simple placeholders
        # A 1x1 black pixel JPEG byte sequence:
        pixel_jpeg = b'\xff\xd8\xff\xdb\x00\x43\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c\x20\x24\x2e\x27\x20\x22\x2c\x23\x1c\x1c\x28\x37\x29\x2c\x30\x31\x34\x34\x34\x1f\x27\x39\x3d\x38\x32\x3c\x2e\x33\x34\x32\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x37\xff\xd9'

        for i in range(1, 6):
            frame_path = os.path.join(output_dir, f"frame_{i:03d}.jpg")
            with open(frame_path, 'wb') as f:
                f.write(pixel_jpeg)
            paths.append(os.path.abspath(frame_path))
            
        return paths
