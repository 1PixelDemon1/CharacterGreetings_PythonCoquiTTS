from app.models.template_manager import TemplateManager
from app.services.greeting_generator import generate_greeting_from_template

tm = TemplateManager("app/db/templates.db")
video_bytes = generate_greeting_from_template(
    template_manager=tm,
    template_id="52341ef2-d6ec-433f-8399-3274d97317c6",
    text="Дружок, я слышал у тебя сегодня день рождения! Я хочу поздравить тебя. Я знаю, что ты крутой парень, добрый, красивый и умный! Помогаешь другим людям в трудную минуту. Ты огромный молодец, пусть у тебя в жизни все будет радостно, легко и дружно!!! С наилучшими пожеланиями твой любимый герой!"
)

with open("result123.mp4", "wb") as f:
    f.write(video_bytes)