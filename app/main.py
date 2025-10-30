import torch
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.api import TTS

# Разрешаем безопасную загрузку конфигурации XTTS
torch.serialization.add_safe_globals([XttsConfig])

# Загружаем модель
tts = TTS(
    model_name="tts_models/multilingual/multi-dataset/xtts_v2",
    progress_bar=True,
    gpu=torch.cuda.is_available()
)

# Генерация
tts.tts_to_file(
    text="Итак, что такое микросервисы? Это метод, при котором приложение разбивается на небольшие, независимые либо слабосвязанные сервисы, которые выполняют определенную задачу или бизнес-задачу.",
    speaker_wav="C:\\Users\\pxldem\\Desktop\\CharacterGreetings_PythonCoquiTTS\\app\\reference.wav",
    language="ru",
    file_path="C:\\Users\\pxldem\\Desktop\\CharacterGreetings_PythonCoquiTTS\\app\\output.wav"
)