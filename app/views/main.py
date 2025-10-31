import os
import uuid
from flask import Blueprint, render_template, request, url_for, send_from_directory

main = Blueprint('main', __name__)

REFERENCES_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'references')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'output')

os.makedirs(REFERENCES_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def split_texts(text_block: str):
    texts = [t.strip() for t in text_block.split('\n\n') if t.strip()]
    if not texts:
        texts = [t.strip() for t in text_block.split('---') if t.strip()]
    return texts

def get_reference_list():
    refs = []
    for f in os.listdir(REFERENCES_FOLDER):
        if f.endswith('.wav'):
            display_name = f.rsplit('.', 1)[0]
            refs.append((f, display_name))
    refs.sort(key=lambda x: x[0])
    return refs

# === Маршрут для главной страницы ===
@main.route('/', methods=['GET', 'POST'])
def index():
    outputs = []
    error = None
    reference_list = get_reference_list()
    selected_ref = None

    if request.method == 'POST':
        text_block = request.form.get('text_block', '').strip()
        new_audio = request.files.get('new_reference')
        selected_ref = request.form.get('existing_reference')

        if new_audio and new_audio.filename.endswith('.wav'):
            safe_name = f"{uuid.uuid4().hex}_{new_audio.filename}"
            ref_path = os.path.join(REFERENCES_FOLDER, safe_name)
            new_audio.save(ref_path)
            selected_ref = safe_name
            reference_list = get_reference_list()

        if not selected_ref or selected_ref not in [r[0] for r in reference_list]:
            error = "Выберите или загрузите аудиосэмпл."
        else:
            ref_path = os.path.join(REFERENCES_FOLDER, selected_ref)
            if not text_block:
                error = "Введите хотя бы один текст."
            else:
                texts = split_texts(text_block)
                if not texts:
                    error = "Не удалось извлечь тексты."
                else:
                    from app.models.tts_model import TTSModel
                    tts_model = TTSModel()
                    for i, text in enumerate(texts, 1):
                        out_filename = f"{uuid.uuid4().hex}.wav"
                        out_path = os.path.join(OUTPUT_FOLDER, out_filename)
                        tts_model.synthesize(
                            text=text,
                            speaker_wav=ref_path,
                            output_path=out_path,
                            language="ru"
                        )
                        outputs.append({
                            'index': i,
                            'text': text,
                            'filename': out_filename
                        })

    return render_template(
        'index.html',
        outputs=outputs,
        error=error,
        reference_list=reference_list,
        selected_ref=selected_ref
    )

# === Маршрут для отдачи СГЕНЕРИРОВАННЫХ аудиофайлов ===
@main.route('/audio/<filename>')
def serve_audio(filename):
    # Защита от path traversal
    if '..' in filename or filename.startswith('/'):
        return "Недопустимое имя файла", 400
    full_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(full_path) or not filename.endswith('.wav'):
        return "Файл не найден", 404
    return send_from_directory(OUTPUT_FOLDER, filename)

# === (Опционально) Маршрут для прослушивания reference ===
@main.route('/reference/<filename>')
def serve_reference(filename):
    if '..' in filename or filename.startswith('/'):
        return "Недопустимое имя файла", 400
    full_path = os.path.join(REFERENCES_FOLDER, filename)
    if not os.path.exists(full_path) or not filename.endswith('.wav'):
        return "Reference не найден", 404
    return send_from_directory(REFERENCES_FOLDER, filename)