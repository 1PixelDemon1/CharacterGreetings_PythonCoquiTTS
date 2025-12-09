"""
Библиотека для генерации синтезированной речи на русском языке.
Поддерживает:
- Разбиение длинных текстов на предложения (nltk==3.7)
- Генерацию по предложениям с последующей склейкой
- Улучшение качества звука
- Работу с байтами (без прямой зависимости от файловой системы)

Требуемые зависимости:
    TTS>=0.22.0
    torch==2.5.1
    torchaudio==2.5.1
    transformers==4.33.0
    pydub==0.25.1
    nltk==3.7
"""

import os
import uuid
import torch
import io
import tempfile
import nltk
from typing import Optional
from TTS.api import TTS
from pydub import AudioSegment
from pydub.effects import low_pass_filter, normalize

# === Инициализация NLTK ===
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# === Глобальные настройки ===
_TTS_MODEL = None
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def _load_tts_model() -> TTS:
    """Загружает и кэширует модель XTTS v2."""
    global _TTS_MODEL
    if _TTS_MODEL is None:
        try:
            from TTS.tts.configs.xtts_config import XttsConfig
            torch.serialization.add_safe_globals([XttsConfig])
        except ImportError:
            pass

        _TTS_MODEL = TTS(
            model_name="tts_models/daswer123/xtts_ru_dvae_100h",
            progress_bar=False,
            gpu=(_DEVICE == "cuda")
        )
    return _TTS_MODEL


def _split_into_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения (русский язык)."""
    return nltk.sent_tokenize(text, language='russian')


def _convert_audio_bytes_to_xtts_format(
    audio_bytes: bytes,
    input_format: Optional[str] = None
) -> bytes:
    """Конвертирует аудио в формат XTTS (22050 Гц, моно, 16 бит, WAV)."""
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=input_format)
    audio = audio.set_frame_rate(22050).set_channels(1).set_sample_width(2)
    buffer = io.BytesIO()
    audio.export(buffer, format="wav")
    return buffer.getvalue()


def _enhance_audio_bytes(audio_bytes: bytes) -> bytes:
    """
    Улучшает качество синтезированной речи:
    - Сильно подавляет высокие частоты (>6.5 кГц), где "резкость"
    - Применяет компрессию для сглаживания динамики
    - Нормализует громкость
    """
    try:
        audio = AudioSegment.from_wav(io.BytesIO(audio_bytes))
        
        # 1. Агрессивный low-pass для устранения "цифровой резкости"
        audio = low_pass_filter(audio, cutoff=6500)  # снизили с 7500 → 6500
        
        # 2. Лёгкая компрессия (сглаживает пики → звук "мягче")
        audio = audio.compress_dynamic_range(
            threshold=-20.0,   # дБ — начинаем сжимать тише этого уровня
            ratio=2.5,         # степень сжатия
            attack=5.0,        # мс — как быстро реагировать на пики
            release=50.0       # мс — как быстро отпускать
        )
        
        # 3. Нормализация с запасом
        audio = normalize(audio, headroom=0.5)  # 0.5 dB headroom → чуть громче и безопасно
        
        # Экспорт
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        return buffer.getvalue()
        
    except Exception as e:
        # При ошибке — возвращаем оригинал
        return audio_bytes


def _concatenate_audio_segments(segments: list[bytes], pause_ms: int) -> bytes:
    """Склеивает аудиосегменты с паузами между ними."""
    if len(segments) == 1:
        return segments[0]
    combined = AudioSegment.empty()
    for i, seg in enumerate(segments):
        audio = AudioSegment.from_wav(io.BytesIO(seg))
        combined += audio
        if i < len(segments) - 1:
            combined += AudioSegment.silent(duration=pause_ms)
    buffer = io.BytesIO()
    combined.export(buffer, format="wav")
    return buffer.getvalue()


def generate_speech(
    text: str,
    reference_audio_bytes: bytes,
    language: str = "ru",
    enhance: bool = True,
    input_format: Optional[str] = None,
    max_sentence_length: int = 180
) -> bytes:
    """
    Генерирует синтезированную речь из текста и reference-аудио.
    
    Параметры:
        text: текст на русском языке
        reference_audio_bytes: байты аудиофайла (любой формат)
        language: язык (по умолчанию "ru")
        enhance: применять улучшение звука (по умолчанию True)
        input_format: формат reference-аудио (если известен)
        max_sentence_length: максимальная длина "предложения"
    
    Возвращает:
        байты аудио в формате WAV
    """
    if not text.strip():
        raise ValueError("Текст не может быть пустым")

    # Разбиваем на предложения
    sentences = _split_into_sentences(text.strip())
    
    # Защита от очень длинных "предложений"
    safe_sentences = []
    for sent in sentences:
        if len(sent) > max_sentence_length:
            words = sent.split()
            chunks = []
            current = []
            for word in words:
                if len(" ".join(current + [word])) <= max_sentence_length:
                    current.append(word)
                else:
                    if current:
                        chunks.append(" ".join(current))
                    current = [word]
            if current:
                chunks.append(" ".join(current))
            safe_sentences.extend(chunks)
        else:
            safe_sentences.append(sent)
    
    sentences = [s.strip() for s in safe_sentences if s.strip()]
    if not sentences:
        raise ValueError("Не удалось извлечь осмысленные предложения")

    # Генерация
    sentence_audios = []
    tts_model = _load_tts_model()

    for sentence in sentences:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as ref_tmp, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out_tmp:

            ref_path = ref_tmp.name
            out_path = out_tmp.name

            try:
                ref_xtts = _convert_audio_bytes_to_xtts_format(
                    reference_audio_bytes, input_format
                )
                with open(ref_path, "wb") as f:
                    f.write(ref_xtts)

                tts_model.tts_to_file(
                    text=sentence,
                    speaker_wav=ref_path,
                    language=language,
                    file_path=out_path
                )

                with open(out_path, "rb") as f:
                    audio_bytes = f.read()

                if enhance:
                    audio_bytes = _enhance_audio_bytes(audio_bytes)

                sentence_audios.append(audio_bytes)

            finally:
                for path in [ref_path, out_path]:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except (OSError, PermissionError):
                        pass

    return _concatenate_audio_segments(sentence_audios, pause_ms=0)