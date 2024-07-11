import os
import requests
import boto3
import base64
import io
from gradio_client import Client
from PIL import Image
from datetime import datetime
import random
import logging
from linebot.models import FollowEvent, MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
import sqlite3
from datetime import datetime, timedelta, date
from openai import OpenAI
client = OpenAI(api_key=os.environ.get('OPENAI_API'))

conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()


# S3クライアントの初期化
s3_client = boto3.client('s3')
S3_BUCKET_NAME = 'fithero'

# Set up logging
logging.basicConfig(filename='error.log', level=logging.WARNING)

# handsomenessレベルごとにプロンプトを設定する関数
def get_prompt_based_on_handsomeness(handsomeness):
    base_prompt = "traditional oil painting style anime illustration. Please generate only one image of the trainer. The background color should be plain without any patterns or extra text. An illustration of a 35-year-old male trainer facing forward, upper body depicted. He has black hair and a slightly bulging nose."
    
    # 髭の有無を指定
    if handsomeness >= 0:
        beard_prompt = " He has no beard."
    else:
        beard_prompt = " He has a beard."
    
    # 服を着せるかどうかを指定
    if handsomeness < 20:
        clothing_prompt = " He is wearing gym clothes."
    else:
        clothing_prompt = " He is shirtless."

    seed_value = " seed is 1242624025"

    # Handsomeness level を 0 から 100 の範囲にスケーリング
    scaled_handsomeness = (handsomeness + 200) / 3
    attractiveness_level = min(max(scaled_handsomeness, 0), 100)

    # scaled_handsomeness に基づいて魅力度を決定
    if attractiveness_level < 0:
        attractiveness = " He is severely overweight, wearing very simple and unkempt gym clothes. He doesn't have any muscle"
    elif attractiveness_level < 25:
        attractiveness = " He is slightly overweight. He doesn't have any muscle"
    elif attractiveness_level < 50:
        attractiveness = " He has a normal build."
    elif attractiveness_level < 75:
        attractiveness = " He is fit."
    else:
        attractiveness = " He is very handsome and well-built."

    attractiveness_level_prompt = f" His attractiveness level is {attractiveness_level} out of 100."

     # 背景の色を設定
    if attractiveness_level < 25:
        background_color = " The background is a dark color."
    elif attractiveness_level < 50:
        background_color = " The background is a neutral color."
    elif attractiveness_level < 75:
        background_color = " The background is a light color."
    else:
        background_color = " The background is a very bright color."

    return base_prompt + attractiveness + beard_prompt + clothing_prompt + attractiveness_level_prompt + background_color + seed_value


# 画像生成関数
def create_trainer_image(handsomeness):
    prompt = get_prompt_based_on_handsomeness(handsomeness)
    logging.error(f"prompt: {prompt}")
    
    # 画像生成のリクエスト
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    print("Generated Image URL:", image_url)
    return image_url


# レスポンス内容を確認し、画像をS3にアップロードする関数
def save_image_to_s3(result, output_filename):
    try:
        response = requests.get(result)
        response.raise_for_status()
        img_data = response.content
        s3_client.upload_fileobj(io.BytesIO(img_data), S3_BUCKET_NAME, output_filename)
        s3_file_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{output_filename}"
        print(f"画像がS3にアップロードされました: {s3_file_url}")
        return s3_file_url
    except Exception as e:
        logging.error(f"画像のアップロードに失敗しました: {e}")
        return None



# 初回イケメントレーナーのご挨拶
def welcome_trainer(line_id, line_bot_api):
    welcome_message = (
        "Thank you for adding me as a friend😊\n"
        "I will be your partner and work hard together with you to achieve your diet goals💪\n"
        "Let me send you my photo📷"
    )
    image_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/image.png" 

    with conn:
        c.execute('INSERT OR IGNORE INTO users (line_id, state) VALUES (?, ?)', (line_id, 'ASK_NAME'))
        c.execute('SELECT id FROM users WHERE line_id = ?', (line_id,))
        user = c.fetchone()
        user_id = user[0]
        c.execute('INSERT INTO trainers (user_id, image_path, handsomeness) VALUES (?, ?, ?)', (user_id, image_url, 0))
        # one_day_ago = (date.today().replace(day=date.today().day - 1)).strftime('%Y-%m-%d')
        # c.execute('INSERT INTO trainer_requests (user_id, request_date) VALUES (?, ?)', (user_id, one_day_ago))
        conn.commit()

    handsome_message = fetch_handsome_message(user_id)

    line_bot_api.push_message(
        to=line_id,
        messages=[
            TextSendMessage(text=welcome_message),
            TextSendMessage(text=handsome_message),
            ImageSendMessage(original_content_url=image_url, preview_image_url=image_url),
            TextSendMessage(text="Then, tell me about your information.\nPlease tell me your name.")
        ]
    )


# トレーナーの状態を判断する関数
def judge_trainer_status(user_id):
    today = datetime.today().date()
    start_of_day = datetime.combine(today, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    end_of_day = datetime.combine(today, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")
    
    # 当日の総カロリーを取得
    total_calories = 0
    c.execute('''
        SELECT SUM(calories) 
        FROM nutritional_records 
        WHERE user_id = ? AND date_time BETWEEN ? AND ?
    ''', (user_id, start_of_day, end_of_day))
    total_calories = c.fetchone()[0]
    
    # ユーザーの目標カロリーを取得
    c.execute('SELECT target_calories FROM users WHERE id = ?', (user_id,))
    target_calories = c.fetchone()[0]

    if total_calories is None:
        print("total_calories=None")
        total_calories=0
    # 目標カロリーと当日の総カロリーをログに出力
    logging.error(f"user_id: {user_id}, total_calories: {total_calories}, target_calories: {target_calories}")

    # 状態を判断
    if total_calories < target_calories:
        logging.error(f"status: good")
        return "good"
    else:
        logging.error(f"status: bad")
        return "bad"


# イケメントレーナーの画像生成関数
def generate_trainer_image(user_id):
    c.execute('SELECT handsomeness FROM trainers WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    last_record = c.fetchone()
    
    if last_record:
        handsomeness = last_record[0]  # 最後のハンサムレベル
    else:
        handsomeness = 0
    
    output_filename = f"trainer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    status = judge_trainer_status(user_id)
    print("status=", status)
    if status == "good":
        handsomeness += 1
    else:
        handsomeness -= 1
    result = create_trainer_image(handsomeness)
    s3_file_url = save_image_to_s3(result, output_filename) if result else None
    save_trainer_to_sql(user_id, s3_file_url, handsomeness)

    print("image_path=", s3_file_url)
    return s3_file_url


# trainersのsqlの行を追加
def save_trainer_to_sql(user_id, s3_file_url, handsomeness):
    if s3_file_url:  # ここでチェック
        c.execute('INSERT INTO trainers (user_id, image_path, handsomeness) VALUES (?, ?, ?)', (user_id, s3_file_url, handsomeness))
        conn.commit()
    else:
        logging.error("s3_file_url is None, cannot save to SQL.")


# ハンサムレベルのメッセージの取得
def fetch_handsome_message(user_id):
    c.execute('SELECT handsomeness FROM trainers WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    handsomeness = c.fetchone()[0]

    # ハンサムレベルメッセージを追加
    handsome_message = f"Handsome level: {handsomeness}"
    return handsome_message


def can_request_trainer(user_id):
    today_date = datetime.now().date()
    c.execute('SELECT request_date FROM trainer_requests WHERE user_id = ?', (user_id,))
    row = c.fetchone()

    if row is not None:  # fetchoneの結果がNoneでないことを確認
        last_request_date = datetime.strptime(row[0], '%Y-%m-%d').date()
        if last_request_date == today_date:
            return False
    return True

def update_request_date(user_id):
    today_date = datetime.now().date().strftime('%Y-%m-%d')
    c.execute('INSERT OR REPLACE INTO trainer_requests (user_id, request_date) VALUES (?, ?)', 
              (user_id, today_date))
    conn.commit()