"""
Сервис генерации поздравлений по шаблонам.
Связывает: TemplateManager, TTS, VideoMixer.
"""

import os
import tempfile
from typing import Optional
from moviepy.editor import VideoFileClip, concatenate_videoclips
from app.models.template_manager import TemplateManager
from app.tts_generator import generate_speech
from app.video_mixer import mix_video_with_audio


def generate_greeting_from_template(
    template_manager: TemplateManager,
    template_id: str,
    text: str,
    fade_duration: float = 1.0,
    tts_volume_boost_db: float = 0.0,
    post_audio_padding: float = 1.0
) -> bytes:
    """
    Генерирует поздравление по шаблону.
    
    Поведение:
      - Intro и Outro: используются как есть (без TTS)
      - Основное видео: накладывается TTS-аудио
      - Всё склеивается в один ролик с fade-out в конце
    """
    # 1. Получаем шаблон
    template = template_manager.get_template(template_id)
    
    # 2. Загружаем reference-аудио
    ref_path = template_manager.get_reference_path(template["reference_id"])
    with open(ref_path, "rb") as f:
        ref_bytes = f.read()
    
    # 3. Генерируем TTS
    tts_audio_bytes = generate_speech(
        text=text,
        reference_audio_bytes=ref_bytes
    )
    
    # 4. Обрабатываем основное видео (с TTS)
    video_path = template_manager.get_video_path(template["video_id"])
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    
    main_video_bytes = mix_video_with_audio(
        video_bytes=video_bytes,
        tts_audio_bytes=tts_audio_bytes,
        fade_duration=0,  # fade-out применится ко всему видео в конце
        tts_volume_boost_db=tts_volume_boost_db,
        post_audio_padding=post_audio_padding
    )
    
    # 5. Собираем все части
    temp_files = []
    clips = []
    
    try:
        # === Intro ===
        if template["intro_id"]:
            intro_path = template_manager.get_video_path(template["intro_id"])
            with open(intro_path, "rb") as f:
                intro_bytes = f.read()
            intro_temp = tempfile.mktemp(suffix=".mp4")
            with open(intro_temp, "wb") as f:
                f.write(intro_bytes)
            temp_files.append(intro_temp)
            clips.append(VideoFileClip(intro_temp))
        
        # === Main ===
        main_temp = tempfile.mktemp(suffix=".mp4")
        with open(main_temp, "wb") as f:
            f.write(main_video_bytes)
        temp_files.append(main_temp)
        clips.append(VideoFileClip(main_temp))
        
        # === Outro ===
        if template["outro_id"]:
            outro_path = template_manager.get_video_path(template["outro_id"])
            with open(outro_path, "rb") as f:
                outro_bytes = f.read()
            outro_temp = tempfile.mktemp(suffix=".mp4")
            with open(outro_temp, "wb") as f:
                f.write(outro_bytes)
            temp_files.append(outro_temp)
            clips.append(VideoFileClip(outro_temp))
        
        # === Склейка ===
        if not clips:
            raise ValueError("Нет видео для склейки")
        
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Применяем fade-out ко всему видео
        if fade_duration > 0 and fade_duration < final_clip.duration:
            final_clip = final_clip.fadeout(fade_duration)
        
        # Экспорт в байты
        output_temp = tempfile.mktemp(suffix=".mp4")
        temp_files.append(output_temp)
        final_clip.write_videofile(
            output_temp,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            logger=None
        )
        
        with open(output_temp, "rb") as f:
            result = f.read()
        
        return result
        
    finally:
        # Закрываем клипы
        for clip in clips:
            clip.close()
        final_clip.close()
        
        # Удаляем временные файлы
        for path in temp_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except (OSError, PermissionError):
                pass