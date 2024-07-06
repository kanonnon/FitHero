import os
import io
import base64
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
    FollowEvent, MessageEvent, TextMessage, TextSendMessage, ImageMessage, ImageSendMessage, TemplateSendMessage, ButtonsTemplate, PostbackTemplateAction, MessageTemplateAction, URITemplateAction
)


load_dotenv()  

line_bot_api = LineBotApi(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

app = Flask(__name__)


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


def get_response_from_gpt_with_img(image_path):
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
                {"type": "text", "text": "画像について説明して"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]}
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content


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


@handler.add(MessageEvent, message=ImageMessage)
def handle_message(event):
    """
    Handle image message event
    """
    message_id = event.message.id
    message_content = line_bot_api.get_message_content(message_id)
    
    with open(f"static/{message_id}.jpg", "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)
    
    image_path = f"static/{message_id}.jpg"
    response_text = get_response_from_gpt_with_img(image_path)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )


if __name__ == "__main__":
    app.run()
