from app.tts_generator import generate_speech

# Загрузка reference
with open("my_voice1.mp3", "rb") as f:
    ref = f.read()

# Длинный текст
text = """
С днём рождения! Желаю тебе ярких впечатлений, веселых приключений и много радостных моментов! Пусть каждый день будет полон сюрпризов и новых открытий, а все твои мечты сбываются. Помни, что ты – волшебник своей жизни, и у тебя все получится!
"""

# Генерация
audio = generate_speech(
    text=text,
    reference_audio_bytes=ref,
    input_format="mp3"
)

# Сохранение
with open("output.wav", "wb") as f:
    f.write(audio)