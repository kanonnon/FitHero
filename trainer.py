import os
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

conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()

# Hugging FaceのAPIエンドポイントを指定
client = Client("https://hysts-controlnet-v1-1.hf.space/")
S3_BUCKET_NAME = 'fithero'

# S3クライアントの初期化
s3_client = boto3.client('s3')

# Set up logging
logging.basicConfig(filename='error.log', level=logging.WARNING)

# 画像のパスとパラメータを指定してAPIを呼び出す関数
def call_api(image_url, prompt):
    try:
        result = client.predict(
            image_url,  # 画像URL
            prompt,  # プロンプト
            "best quality, extremely detailed",  # 追加のプロンプト
            "longbody, lowres, bad anatomy, bad hands, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality",  # ネガティブプロンプト
            1,  # 生成する画像の数
            512,  # 画像の解像度
            50,  # ステップ数
            7.5,  # ガイダンススケール
            random.randint(0, 1000000),  # ランダムなシード値
            api_name="/ip2p"  # APIのエンドポイント名
        )
        print("APIリクエストが成功しました。")
        return result
    except Exception as e:
        logging.error(f"API呼び出しに失敗しました: {e}")
        return None

# レスポンス内容を確認し、画像をS3にアップロードする関数
def save_image_to_s3(result, output_filename):
    if result and os.path.isdir(result):
        try:
            for root, dirs, files in os.walk(result):
                for file in files:
                    if file.endswith(('.png', '.jpg', '.jpeg')):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'rb') as img_file:
                            s3_client.upload_fileobj(img_file, S3_BUCKET_NAME, output_filename)
                            s3_file_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{output_filename}"
                            print(f"画像がS3にアップロードされました: {s3_file_url}")
                            return s3_file_url
        except Exception as e:
            logging.error(f"画像のアップロードに失敗しました: {e}")
    else:
        logging.error("画像生成に失敗しました。指定されたファイルが存在しないか、他のエラーが発生しています。")
    return None

# 初回イケメントレーナーのご挨拶
def welcome_trainer(line_id, line_bot_api):
    welcome_message = (
        "Thank you for adding me as a friend😊\n"
        "I will be your partner and work hard together with you to achieve your diet goals💪\n"
        "Let me send you my photo📷"
    )
    image_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/man2.png"  # S3にアップロードされたman2.pngのURL

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
    c.execute('SELECT image_path, handsomeness FROM trainers WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    last_record = c.fetchone()
    
    if last_record:
        image_url = last_record[0]  # 最後の画像URL
        handsomeness = last_record[1]  # 最後のハンサムレベル
    else:
        image_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/man2.png"  # デフォルト画像URL
        handsomeness = 0

    output_filename = f"trainer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    status = judge_trainer_status(user_id)
    print("status=", status)
    if status == "good":
        handsomeness += 1
        result = call_api(
            image_url,
            "The same person, facing forward, enhance his appearance slightly to make him more handsome and muscular. Improve facial symmetry, skin texture, and brightness subtly. Ensure he retains a natural look. Make his T-shirt color slightly bluer."
        )
    else:
        handsomeness -= 1
        result = call_api(
            image_url,
            "The same person, facing forward, adjust his appearance slightly to look less handsome and slightly overweight. Introduce minor asymmetry, rougher skin texture, and subtle signs of aging. Ensure he retains a natural look. Make him look older and slightly chubby."
        )
    s3_file_url = save_image_to_s3(result, output_filename) if result else None
    save_trainer_to_sql(user_id, s3_file_url, handsomeness)

    print("last_image_path=", image_url)
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