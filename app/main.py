import logging
import os
import shutil
from uuid import uuid4, UUID

from fastapi import (FastAPI, HTTPException, Form, File, Depends,
                     UploadFile, status)
from fastapi.responses import FileResponse
import ffmpeg
from sqlalchemy.orm.session import Session

from database import get_db
from models import User, Audio
from config import DOWNLOAD_HOST, DOWNLOAD_PORT

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

app = FastAPI()


@app.post('/create_user')
def create_user(user_name: str,
                db: Session = Depends(get_db)) -> dict:
    """Добовление нового пользователя в базу данных."""
    user_id = uuid4()
    access_token = str(uuid4())
    user = User(id=user_id, name=user_name, access_token=access_token)
    db.add(user)
    db.commit()
    logging.info('Новый пользователь добавлен в базу данных')
    return {
        'user_id': user_id,
        'access_token': access_token,
    }


def wav_to_mp3(audio_file: File, audio_id: UUID) -> dict:
    audio_folder = '/uploads'
    audio_path = f'{audio_folder}/{audio_id}.wav'
    mp3_path = f'{audio_folder}/{audio_id}.mp3'
    if 'audio/wav' in audio_file.content_type:
        try:
            with open(audio_path, 'wb') as file:
                shutil.copyfileobj(audio_file.file, file)
            ffmpeg.input(audio_path).output(mp3_path).run()
            return {
                'mp3_path': mp3_path,
                'audio_path': audio_path,
            }
        except ffmpeg.Error as e:
            logging.error(e)
            raise e
    message = 'Неверный формат аудио'
    raise TypeError(message)


@app.post('/add_audio')
def add_audio(user_id: str = Form(...),
              access_token: str = Form(...),
              audio_file: UploadFile = File(...),
              db: Session = Depends(get_db)) -> dict:
    """Получение mp3, добавление в базу данных"""
    user = db.query(User).filter(User.id == user_id,
                                 User.access_token == access_token).first()
    if user is None:
        message = 'Пользователь не найден в базе данных'
        logging.error(message)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=message)
    logging.info('Получен пользователь из базы данных')
    audio_id = uuid4()
    audio_mp3 = wav_to_mp3(audio_file, audio_id)
    audio = Audio(id=audio_id,
                  user_id=user_id,
                  file_path=audio_mp3.get('mp3_path'))
    db.add(audio)
    db.commit()
    logging.info('Mp3 запись добавлена в базу данных')
    os.remove(audio_mp3.get('audio_path'))
    return {
        'download_url':
            (f'https://{DOWNLOAD_HOST}:{DOWNLOAD_PORT}'
             f'/record?id={audio_id}&user={user_id}')
    }


@app.get('/record')
def download_record(download_url: str,
                    db: Session = Depends(get_db)) -> FileResponse:
    """Получение из URL данных и скачивание файла"""
    try:
        audio = download_url.rindex('id=')
        user = download_url.rindex('user=')
        audio_id = download_url[audio + 3:audio + 39]
        user_id = download_url[user + 5:user + 41]
        audio = db.query(Audio).filter(Audio.id == audio_id,
                                       Audio.user_id == user_id).first()

        if not audio:
            message = 'Запись не найдена в базе данных'
            logging.error(message)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=message)

        return FileResponse(audio.file_path)
    except Exception:
        message = 'Ошибка при скачивании записи'
        logging.error(message)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=message)
