# app/views/main.py

import os
import uuid
from flask import Blueprint, render_template, request, url_for, send_from_directory
from pydub import AudioSegment

main = Blueprint('main', __name__)

REFERENCES_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'references')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'output')

os.makedirs(REFERENCES_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def convert_to_xtts_wav(input_path: str, output_path: str):
    """
    Конвертирует любой аудиофайл в формат, подходящий для XTTS v2:
    - WAV
    - 22050 Гц
    - моно
    - 16 бит
    """
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(22050).set_channels(1).set_sample_width(2)  # 2 bytes = 16 bit
    audio.export(output_path, format="wav")

def get_reference_list():
    refs = []
    for f in os.listdir(REFERENCES_FOLDER):
        if f.endswith('.wav'):
            display_name = f.rsplit('.', 1)[0]
            refs.append((f, display_name))
    refs.sort(key=lambda x: x[0])
    return refs

@main.route('/', methods=['GET', 'POST'])
def index():
    output_file = None
    error = None
    reference_list = get_reference_list()
    selected_ref = None

    if request.method == 'POST':
        text = request.form.get('text', '').strip()
        new_audio = request.files.get('new_reference')
        selected_ref = request.form.get('existing_reference')

        if new_audio and new_audio.filename:
            # Определяем расширение оригинального файла
            original_ext = os.path.splitext(new_audio.filename)[1].lower()
            if not original_ext:
                original_ext = ".tmp"

            # Сохраняем временный файл
            temp_input = os.path.join(REFERENCES_FOLDER, f"{uuid.uuid4().hex}{original_ext}")
            new_audio.save(temp_input)

            # Конвертируем в нужный WAV
            wav_name = f"{uuid.uuid4().hex}.wav"
            wav_path = os.path.join(REFERENCES_FOLDER, wav_name)

            try:
                convert_to_xtts_wav(temp_input, wav_path)
                selected_ref = wav_name
                reference_list = get_reference_list()
            except Exception as e:
                error = f"Ошибка конвертации аудио: {str(e)}"
            finally:
                # Удаляем временный файл
                if os.path.exists(temp_input):
                    os.remove(temp_input)

            if error:
                return render_template(
                    'index.html',
                    error=error,
                    reference_list=reference_list,
                    selected_ref=selected_ref
                )

        # Валидация reference
        if not selected_ref or selected_ref not in [r[0] for r in reference_list]:
            error = "Выберите или загрузите аудиосэмпл."
        elif not text:
            error = "Введите текст для синтеза."
        else:
            ref_path = os.path.join(REFERENCES_FOLDER, selected_ref)
            out_filename = f"{uuid.uuid4().hex}.wav"
            out_path = os.path.join(OUTPUT_FOLDER, out_filename)

            from app.models.tts_model import TTSModel
            tts_model = TTSModel()
            tts_model.synthesize(
                text=text,
                speaker_wav=ref_path,
                output_path=out_path,
                language="ru"
            )
            output_file = out_filename

    return render_template(
        'index.html',
        output_file=output_file,
        error=error,
        reference_list=reference_list,
        selected_ref=selected_ref
    )

@main.route('/audio/<filename>')
def serve_audio(filename):
    if '..' in filename or filename.startswith('/'):
        return "Недопустимое имя файла", 400
    full_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.isfile(full_path) or not filename.endswith('.wav'):
        return "Аудиофайл не найден", 404
    return send_from_directory(OUTPUT_FOLDER, filename)

@main.route('/reference/<filename>')
def serve_reference(filename):
    if '..' in filename or filename.startswith('/'):
        return "Недопустимое имя файла", 400
    full_path = os.path.join(REFERENCES_FOLDER, filename)
    if not os.path.isfile(full_path) or not filename.endswith('.wav'):
        return "Reference не найден", 404
    return send_from_directory(REFERENCES_FOLDER, filename)