from app.tts_generator import generate_speech
from app.video_mixer import mix_video_with_audio

# Генерация TTS
with open("my_voice.mp3", "rb") as f:
    ref = f.read()
tts_audio = generate_speech("Привет! Я говорю поверх фоновой музыки.", ref)

# Загрузка видео
with open("Test_65s.mp4", "rb") as f:
    video = f.read()

# Получение итогового видео в байтах
video_bytes = mix_video_with_audio(
    video_bytes=video,
    tts_audio_bytes=tts_audio,
    fade_duration=0.8,
    tts_volume_boost_db=3.0
)

# Сохранение (опционально)
with open("result.mp4", "wb") as f:
    f.write(video_bytes)