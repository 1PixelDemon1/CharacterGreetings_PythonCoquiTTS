"""
Управление шаблонами поздравлений с использованием SQLite.
"""

import os
import sqlite3
import uuid
from typing import Optional, Tuple, List
from app.tts_generator import generate_speech
from app.video_mixer import mix_video_with_audio


class TemplateManager:
    def __init__(self, db_path: str = "app/db/templates.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Создаёт таблицы, если их нет."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS ReferenceAudioFiles (
                    Id TEXT PRIMARY KEY,
                    FilePath TEXT NOT NULL,
                    Description TEXT
                );
                CREATE TABLE IF NOT EXISTS VideoFiles (
                    Id TEXT PRIMARY KEY,
                    FilePath TEXT NOT NULL,
                    Description TEXT
                );
                CREATE TABLE IF NOT EXISTS Templates (
                    Id TEXT PRIMARY KEY,
                    IntroId TEXT NULL,
                    VideoId TEXT NOT NULL,
                    OutroId TEXT NULL,
                    ReferenceId TEXT NOT NULL,
                    Description TEXT,
                    FOREIGN KEY (IntroId) REFERENCES VideoFiles (Id) ON DELETE SET NULL,
                    FOREIGN KEY (VideoId) REFERENCES VideoFiles (Id) ON DELETE CASCADE,
                    FOREIGN KEY (OutroId) REFERENCES VideoFiles (Id) ON DELETE SET NULL,
                    FOREIGN KEY (ReferenceId) REFERENCES ReferenceAudioFiles (Id) ON DELETE CASCADE
                );
            """)
            conn.commit()

    # --- Методы для ReferenceAudioFiles ---
    def add_reference(self, file_path: str, description: Optional[str] = None) -> str:
        ref_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO ReferenceAudioFiles (Id, FilePath, Description) VALUES (?, ?, ?)",
                (ref_id, file_path, description)
            )
        return ref_id

    def get_reference_path(self, ref_id: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT FilePath FROM ReferenceAudioFiles WHERE Id = ?", (ref_id,)
            ).fetchone()
        if not row:
            raise ValueError(f"Reference с ID {ref_id} не найден")
        return row[0]

    # --- Методы для VideoFiles ---
    def add_video(self, file_path: str, description: Optional[str] = None) -> str:
        vid_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO VideoFiles (Id, FilePath, Description) VALUES (?, ?, ?)",
                (vid_id, file_path, description)
            )
        return vid_id

    def get_video_path(self, vid_id: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT FilePath FROM VideoFiles WHERE Id = ?", (vid_id,)
            ).fetchone()
        if not row:
            raise ValueError(f"Видео с ID {vid_id} не найдено")
        return row[0]

    # --- Методы для Templates ---
    def add_template(
        self,
        video_id: str,
        reference_id: str,
        intro_id: Optional[str] = None,
        outro_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        template_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO Templates (Id, IntroId, VideoId, OutroId, ReferenceId, Description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (template_id, intro_id, video_id, outro_id, reference_id, description))
        return template_id

    def get_template(self, template_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT IntroId, VideoId, OutroId, ReferenceId, Description
                FROM Templates WHERE Id = ?
            """, (template_id,)).fetchone()
        if not row:
            raise ValueError(f"Шаблон с ID {template_id} не найден")
        return {
            "intro_id": row[0],
            "video_id": row[1],
            "outro_id": row[2],
            "reference_id": row[3],
            "description": row[4]
        }