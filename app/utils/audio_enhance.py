# app/utils/audio_enhance.py

from pydub import AudioSegment
from pydub.effects import low_pass_filter, normalize
import os

def enhance_tts_audio(input_wav_path: str, output_wav_path: str):
    try:
        audio = AudioSegment.from_wav(input_wav_path)
        audio = low_pass_filter(audio, cutoff=7500)
        audio = normalize(audio, headroom=1.0)
        audio.export(output_wav_path, format="wav")
    except Exception as e:
        if os.path.exists(input_wav_path):
            with open(output_wav_path, 'wb') as out, open(input_wav_path, 'rb') as orig:
                out.write(orig.read())
        raise e