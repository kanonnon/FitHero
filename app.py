import os
import sqlite3
from datetime import datetime, date
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import FollowEvent, MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage

from registration import handle_user_registration
from gpt import calc_nutritional_info_from_image, create_sql_query, create_trainer_advice
from utils import extract_text_between
from trainer2 import generate_trainer_image, welcome_trainer, fetch_handsome_message, can_request_trainer, update_request_date

load_dotenv()

line_bot_api = LineBotApi(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

app = Flask(__name__)

conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()


@app.route("/")
def hello_world():
    return "hello world!"


@app.route("/callback", methods=['POST'])
def callback():
    """
    Callback function for LINE webhook
    """
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(FollowEvent)
def handle_follow(event):
    """
    Handle follow event
    """
    line_id = event.source.user_id
    welcome_trainer(line_id, line_bot_api)


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """
    Handle text message
    """
    line_id = event.source.user_id
    text = event.message.text

    if text == "初回":
        welcome_trainer(line_id, line_bot_api)
        return
    handle_user_registration(line_id, text, event.reply_token, line_bot_api)
    
    c.execute('SELECT id FROM users WHERE line_id = ?', (line_id,))
    user = c.fetchone()
    user_id = user[0]

    if text == "trainer":
        if can_request_trainer(user_id):
            trainer_advice = create_trainer_advice(user_id)
            trainer_advice = extract_text_between(trainer_advice, "#[start]", "#[end]")
            line_bot_api.reply_message(
                    event.reply_token,
                    [
                        TextSendMessage(text=trainer_advice)
                    ]
            )
            s3_file_url = generate_trainer_image(user_id)
            if s3_file_url:
                line_bot_api.reply_message(
                    event.reply_token,
                    [
                        TextSendMessage(text="Here is your trainer😄"),
                        TextSendMessage(text=fetch_handsome_message(user_id)),
                        ImageSendMessage(original_content_url=s3_file_url, preview_image_url=s3_file_url)
                    ]
                )
                update_request_date(user_id)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    [TextSendMessage(text="Something went wrong. Please try again🙏")]
                )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(text="You can only request this once per day😞")]
            )
        return
    
        # 練習用
        # trainer_advice = create_trainer_advice(user_id)
        #     trainer_advice = extract_text_between(trainer_advice, "#[start]", "#[end]")
        #     line_bot_api.reply_message(
        #             event.reply_token,
        #             [
        #                 TextSendMessage(text=trainer_advice)
        #             ]
        #     )
        # s3_file_url = generate_trainer_image(user_id)
        # if s3_file_url:
        #     line_bot_api.reply_message(
        #         event.reply_token,
        #         [
        #             TextSendMessage(text="Here is your trainer!"),
        #             TextSendMessage(text=fetch_handsome_message(user_id)),
        #             ImageSendMessage(original_content_url=s3_file_url, preview_image_url=s3_file_url)
        #         ]
        #     )
        #     update_request_date(user_id)
        # else:
        #     line_bot_api.reply_message(
        #         event.reply_token,
        #         [TextSendMessage(text="Something went wrong. Please try again.")]
        #     )
        # return



@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """
    Handle image message
    """
    message_id = event.message.id
    line_id = event.source.user_id
    message_content = line_bot_api.get_message_content(message_id)

    c.execute('SELECT id FROM users WHERE line_id = ?', (line_id,))
    user = c.fetchone()
    user_id = user[0]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(f"static/{message_id}.jpg", "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)
    
    image_path = f"static/{message_id}.jpg"

    nutritional_info = calc_nutritional_info_from_image(image_path)
    nutritional_info = extract_text_between(nutritional_info, "#{start}", "#{end}")
    sql_query = create_sql_query(user_id, current_time, nutritional_info)
    sql_query = extract_text_between(sql_query, "```sql", "```")
    
    c.execute(sql_query)
    conn.commit()

    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    end_of_day = datetime.combine(today, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")

    c.execute('''
        SELECT 
            SUM(calories), 
            SUM(protein), 
            SUM(fat), 
            SUM(carbohydrates), 
            SUM(dietary_fiber) 
        FROM nutritional_records 
        WHERE user_id = ? AND date_time BETWEEN ? AND ?
    ''', (user_id, start_of_day, end_of_day))
    total_nutrition = c.fetchone()

    total_nutrition_message = (
        f"【Today's Total Nutritional Value:】\n"
        f"🔥 Calories: {total_nutrition[0]:.2f} kcal\n"
        f"💪 Protein: {total_nutrition[1]:.2f} g\n"
        f"🥑 Fat: {total_nutrition[2]:.2f} g\n"
        f"🍞 Carbohydrates: {total_nutrition[3]:.2f} g\n"
        f"🌾 Dietary Fiber: {total_nutrition[4]:.2f} g"
    )

    line_bot_api.reply_message(
        event.reply_token,
        [TextSendMessage(text=nutritional_info), TextSendMessage(text=total_nutrition_message)]
    )


if __name__ == "__main__":
    app.run(debug=True)
