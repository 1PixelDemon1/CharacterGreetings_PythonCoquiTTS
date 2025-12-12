import os
import io
import tempfile
from typing import Union
from moviepy.editor import VideoFileClip, AudioFileClip, AudioClip
from pydub import AudioSegment as PydubAudio


def mix_video_with_audio(
    video_bytes: bytes,
    tts_audio_bytes: bytes,
    fade_duration: float = 1.0,
    tts_volume_boost_db: float = 0.0,
    post_audio_padding: float = 1.0  # ← НОВЫЙ ПАРАМЕТР
) -> bytes:
    """
    Смешивает оригинальное аудио и TTS, и оставляет видео работать ещё post_audio_padding секунд после конца TTS.
    
    Параметры:
        video_bytes: байты видео
        tts_audio_bytes: байты TTS-аудио
        fade_duration: длительность fade-out
        tts_volume_boost_db: усиление TTS
        post_audio_padding: сколько секунд держать видео после окончания TTS (по умолчанию 1.0)
    
    Возвращает:
        байты итогового видео
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vid_tmp, \
         tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tts_tmp, \
         tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as orig_audio_tmp:

        video_path = vid_tmp.name
        tts_path = tts_tmp.name
        orig_audio_path = orig_audio_tmp.name

        try:
            with open(video_path, "wb") as f:
                f.write(video_bytes)
            with open(tts_path, "wb") as f:
                f.write(tts_audio_bytes)

            video = VideoFileClip(video_path)
            has_original_audio = video.audio is not None

            if has_original_audio:
                video.audio.write_audiofile(orig_audio_path, logger=None)
            else:
                silent = PydubAudio.silent(duration=int(video.duration * 1000))
                silent.export(orig_audio_path, format="wav")

            tts_audio_clip = AudioFileClip(tts_path)
            tts_duration = tts_audio_clip.duration

            # === Вычисляем итоговую длительность ===
            target_duration = tts_duration + post_audio_padding
            if video.duration < target_duration:
                # Если видео короче — обрезаем цель до длины видео
                target_duration = video.duration

            # Обрезаем видео до target_duration
            final_video = video.subclip(0, target_duration)

            # === Обработка аудио ===
            # Оригинальное аудио — обрезаем до target_duration
            if has_original_audio:
                orig_pydub = PydubAudio.from_wav(orig_audio_path)
                orig_duration_ms = len(orig_pydub)
                target_duration_ms = int(target_duration * 1000)
                if orig_duration_ms > target_duration_ms:
                    orig_pydub = orig_pydub[:target_duration_ms]
                elif orig_duration_ms < target_duration_ms:
                    silence = PydubAudio.silent(duration=target_duration_ms - orig_duration_ms)
                    orig_pydub = orig_pydub + silence
            else:
                orig_pydub = PydubAudio.silent(duration=int(target_duration * 1000))

            # TTS — обрезаем до tts_duration (не продлеваем!)
            tts_pydub = PydubAudio.from_wav(tts_path)
            tts_duration_ms = len(tts_pydub)
            target_tts_ms = int(tts_duration * 1000)
            if tts_duration_ms > target_tts_ms:
                tts_pydub = tts_pydub[:target_tts_ms]

            # Добавляем тишину после TTS до конца target_duration
            tts_total_ms = len(tts_pydub)
            if tts_total_ms < int(target_duration * 1000):
                silence = PydubAudio.silent(duration=int(target_duration * 1000) - tts_total_ms)
                tts_pydub = tts_pydub + silence

            # Усиление TTS
            if tts_volume_boost_db != 0:
                tts_pydub += tts_volume_boost_db

            # Микс
            mixed_audio = orig_pydub.overlay(tts_pydub)
            mixed_path = tempfile.mktemp(suffix=".wav")
            mixed_audio.export(mixed_path, format="wav")
            mixed_audio_clip = AudioFileClip(mixed_path)

            try:
                # Fade-out к концу видео
                if fade_duration > 0 and fade_duration < final_video.duration:
                    final_video = final_video.fadeout(fade_duration)

                final_video = final_video.set_audio(mixed_audio_clip)

                output_temp = tempfile.mktemp(suffix=".mp4")
                final_video.write_videofile(
                    output_temp,
                    codec="libx264",
                    audio_codec="aac",
                    temp_audiofile="temp-audio.m4a",
                    remove_temp=True,
                    logger=None
                )

                with open(output_temp, "rb") as f:
                    result_bytes = f.read()
                if os.path.exists(output_temp):
                    os.remove(output_temp)

                return result_bytes

            finally:
                final_video.close()
                mixed_audio_clip.close()
                if has_original_audio:
                    video.audio.close()
                video.close()
                tts_audio_clip.close()
                if os.path.exists(mixed_path):
                    os.remove(mixed_path)

        finally:
            for path in [video_path, tts_path, orig_audio_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except (OSError, PermissionError):
                        pass