# app/views/main.py

import os
import uuid
import re
import io
from flask import Blueprint, render_template, request, url_for, send_from_directory, jsonify
from pydub import AudioSegment
from app.utils.audio_enhance import enhance_tts_audio

main = Blueprint('main', __name__)

REFERENCES_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'references')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'output')

os.makedirs(REFERENCES_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def is_valid_filename(filename: str) -> bool:
    if not filename.endswith('.wav'):
        return False
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', filename):
        return False
    if filename.startswith('.'):
        return False
    return True

def convert_bytes_to_xtts_wav(audio_bytes: bytes, input_format: str, output_path: str):
    """Конвертирует байты аудио в XTTS-совместимый WAV (22050 Гц, моно, 16 бит)"""
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=input_format)
    audio = audio.set_frame_rate(22050).set_channels(1).set_sample_width(2)
    audio.export(output_path, format="wav")

def get_reference_list():
    refs = []
    for f in os.listdir(REFERENCES_FOLDER):
        if f.endswith('.wav'):
            display_name = f.rsplit('.', 1)[0]
            refs.append((f, display_name))
    refs.sort(key=lambda x: x[0])
    return refs

# === Главная страница ===
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
            original_ext = os.path.splitext(new_audio.filename)[1].lower() or ".tmp"
            temp_input = os.path.join(REFERENCES_FOLDER, f"{uuid.uuid4().hex}{original_ext}")
            new_audio.save(temp_input)

            wav_name = f"{uuid.uuid4().hex}.wav"
            wav_path = os.path.join(REFERENCES_FOLDER, wav_name)

            try:
                audio_bytes = open(temp_input, 'rb').read()
                fmt = original_ext.lstrip('.')
                if fmt == '.tmp':
                    fmt = 'mp3'  # fallback
                convert_bytes_to_xtts_wav(audio_bytes, fmt, wav_path)
                selected_ref = wav_name
                reference_list = get_reference_list()
            except Exception as e:
                error = f"Ошибка конвертации аудио: {str(e)}"
            finally:
                if os.path.exists(temp_input):
                    os.remove(temp_input)

            if error:
                return render_template(
                    'index.html',
                    error=error,
                    reference_list=reference_list,
                    selected_ref=selected_ref
                )

        if not selected_ref or selected_ref not in [r[0] for r in reference_list]:
            error = "Выберите или загрузите аудиосэмпл."
        elif not text:
            error = "Введите текст для синтеза."
        else:
            ref_path = os.path.join(REFERENCES_FOLDER, selected_ref)
            temp_output = f"{uuid.uuid4().hex}_temp.wav"
            temp_path = os.path.join(OUTPUT_FOLDER, temp_output)
            final_output = f"{uuid.uuid4().hex}.wav"
            final_path = os.path.join(OUTPUT_FOLDER, final_output)

            from app.models.tts_model import TTSModel
            tts_model = TTSModel()
            tts_model.synthesize(
                text=text,
                speaker_wav=ref_path,
                output_path=temp_path,
                language="ru"
            )

            try:
                enhance_tts_audio(temp_path, final_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.rename(temp_path, final_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            output_file = final_output

    return render_template(
        'index.html',
        output_file=output_file,
        error=error,
        reference_list=reference_list,
        selected_ref=selected_ref
    )

# === Скачивание reference ===
@main.route('/reference/<filename>')
def serve_reference(filename):
    if not is_valid_filename(filename):
        return "Недопустимое имя файла", 400
    full_path = os.path.join(REFERENCES_FOLDER, filename)
    if not os.path.isfile(full_path):
        return "Reference не найден", 404
    return send_from_directory(REFERENCES_FOLDER, filename, as_attachment=True)

# === Переименование reference ===
@main.route('/api/reference/rename', methods=['POST'])
def rename_reference():
    try:
        data = request.get_json()
        old_name = data.get('old_name')
        new_name = data.get('new_name')

        if not old_name or not new_name:
            return jsonify({"error": "old_name и new_name обязательны"}), 400
        if not new_name.endswith('.wav'):
            new_name += '.wav'
        if not is_valid_filename(old_name) or not is_valid_filename(new_name):
            return jsonify({"error": "Недопустимое имя файла"}), 400

        old_path = os.path.join(REFERENCES_FOLDER, old_name)
        new_path = os.path.join(REFERENCES_FOLDER, new_name)

        if not os.path.isfile(old_path):
            return jsonify({"error": "Исходный файл не найден"}), 404
        if os.path.exists(new_path):
            return jsonify({"error": "Файл с новым именем уже существует"}), 400

        os.rename(old_path, new_path)
        return jsonify({"success": True, "new_name": new_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Обновление reference (без временных файлов на диске) ===
@main.route('/api/reference/update', methods=['POST'])
def update_reference():
    try:
        ref_name = request.form.get('ref_name')
        new_file = request.files.get('new_file')

        if not ref_name or not new_file:
            return jsonify({"error": "ref_name и new_file обязательны"}), 400
        if not ref_name.endswith('.wav') or not is_valid_filename(ref_name):
            return jsonify({"error": "Недопустимое имя reference"}), 400

        ref_path = os.path.join(REFERENCES_FOLDER, ref_name)
        if not os.path.isfile(ref_path):
            return jsonify({"error": "Reference не найден"}), 404

        audio_bytes = new_file.read()
        if not audio_bytes:
            return jsonify({"error": "Пустой файл"}), 400

        filename = new_file.filename.lower()
        if filename.endswith('.mp3'):
            fmt = 'mp3'
        elif filename.endswith('.wav'):
            fmt = 'wav'
        elif filename.endswith('.ogg'):
            fmt = 'ogg'
        elif filename.endswith('.flac'):
            fmt = 'flac'
        elif filename.endswith('.m4a') or filename.endswith('.aac'):
            fmt = 'mp4'
        else:
            fmt = 'mp3'  # fallback

        convert_bytes_to_xtts_wav(audio_bytes, fmt, ref_path)
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": f"Ошибка обновления: {str(e)}"}), 500

# === Отдача сгенерированного аудио ===
@main.route('/audio/<filename>')
def serve_audio(filename):
    if '..' in filename or filename.startswith('/'):
        return "Недопустимое имя файла", 400
    full_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.isfile(full_path) or not filename.endswith('.wav'):
        return "Аудиофайл не найден", 404
    return send_from_directory(OUTPUT_FOLDER, filename)

# === Публичный API синтеза ===
@main.route('/api/synthesize', methods=['POST'])
def api_synthesize():
    try:
        data = request.get_json()
        
        reference_id = data.get('reference_id')
        text = data.get('text', '').strip()

        if not reference_id:
            return jsonify({"error": "Поле 'reference_id' обязательно"}), 400
        if not text:
            return jsonify({"error": "Поле 'text' обязательно"}), 400
        if not is_valid_filename(reference_id):
            return jsonify({"error": "Недопустимый reference_id"}), 400

        ref_path = os.path.join(REFERENCES_FOLDER, reference_id)
        if not os.path.isfile(ref_path):
            return jsonify({"error": "Reference не найден"}), 404

        temp_output = f"{uuid.uuid4().hex}_temp.wav"
        temp_path = os.path.join(OUTPUT_FOLDER, temp_output)
        final_output = f"{uuid.uuid4().hex}.wav"
        final_path = os.path.join(OUTPUT_FOLDER, final_output)

        from app.models.tts_model import TTSModel
        tts_model = TTSModel()
        tts_model.synthesize(
            text=text,
            speaker_wav=ref_path,
            output_path=temp_path,
            language="ru"
        )

        try:
            enhance_tts_audio(temp_path, final_path)
        except Exception:
            if os.path.exists(temp_path):
                os.rename(temp_path, final_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return send_from_directory(OUTPUT_FOLDER, final_output, mimetype='audio/wav')
    except Exception as e:
        return jsonify({"error": f"Внутренняя ошибка: {str(e)}"}), 500