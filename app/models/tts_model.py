import os
from TTS.api import TTS
import torch

class TTSModel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TTSModel, cls).__new__(cls)
            cls._instance.tts = None
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        if self.tts is None:
            print("Загрузка XTTS v2...")
            # Если вы на PyTorch >= 2.6 — раскомментируйте следующие строки:
            # from TTS.tts.configs.xtts_config import XttsConfig
            # torch.serialization.add_safe_globals([XttsConfig])

            self.tts = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=False,
                gpu=torch.cuda.is_available()
            )
            print("Модель загружена.")

    def synthesize(self, text: str, speaker_wav: str, output_path: str, language: str = "ru"):
        self.tts.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=output_path
        )