import os
import io
import base64
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    FollowEvent, MessageEvent, TextMessage, TextSendMessage, ImageMessage
)


load_dotenv()

line_bot_api = LineBotApi(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

app = Flask(__name__)

conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()


def encode_image(image_data):
    """
    Encode image data to base64
    """
    return base64.b64encode(image_data).decode("utf-8")


def resize_image(image_path, new_size=(512, 512)):
    """
    Resize image to new size
    """
    with Image.open(image_path) as img:
        resized_img = img.resize(new_size)
        img_byte_arr = io.BytesIO()
        resized_img.save(img_byte_arr, format=img.format)
        img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr


def get_response_from_gpt_with_img(image_path, prompt):
    """
    Get response from GPT-4o with image
    """
    resized_image_data = resize_image(image_path)
    base64_image = encode_image(resized_image_data)

    client = OpenAI(api_key=os.environ.get('OPENAI_API'))

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a handsome gym trainer. You gently help your clients lose weight."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]}
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content


def initiate_user_registration(user_id, reply_token):
    """
    Initiate user registration
    """
    c.execute('INSERT OR IGNORE INTO users (id, state) VALUES (?, ?)', (user_id, 'ASK_NAME'))
    conn.commit()
    line_bot_api.reply_message(
        reply_token, TextSendMessage(text="Hello! Please tell me your name.")
    )


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
    user_id = event.source.user_id
    initiate_user_registration(user_id, event.reply_token)


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """
    Handle text message
    """
    user_id = event.source.user_id
    text = event.message.text

    c.execute('SELECT state FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()

    if user:
        state = user[0]

        if state == 'ASK_NAME':
            c.execute('UPDATE users SET name = ?, state = ? WHERE id = ?', (text, 'ASK_HEIGHT', user_id))
            conn.commit()
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Thank you! What is your height (in cm)?")
            )
        elif state == 'ASK_HEIGHT':
            c.execute('UPDATE users SET height = ?, state = ? WHERE id = ?', (float(text), 'ASK_CURRENT_WEIGHT', user_id))
            conn.commit()
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Thank you! What is your current weight (in kg)?")
            )
        elif state == 'ASK_CURRENT_WEIGHT':
            c.execute('UPDATE users SET current_weight = ?, state = ? WHERE id = ?', (float(text), 'ASK_TARGET_WEIGHT', user_id))
            conn.commit()
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="Thank you! What is your target weight (in kg)?")
            )
        elif state == 'ASK_TARGET_WEIGHT':
            c.execute('UPDATE users SET target_weight = ?, state = ? WHERE id = ?', (float(text), 'REGISTERED', user_id))
            conn.commit()
            with open('explanation.txt', 'r', encoding='utf-8') as file:
                explanation = file.read()
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text=f"Registration complete!\n{explanation}")
            )
    else:
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text="You are already registered!")
        )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """
    Handle image message
    """
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    
    with open(f"static/{message_id}.jpg", "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)
    
    image_path = f"static/{message_id}.jpg"
    
    with open('prompt.txt', 'r', encoding='utf-8') as file:
        prompt = file.read()

    response_text = get_response_from_gpt_with_img(image_path, prompt)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )


if __name__ == "__main__":
    app.run()
