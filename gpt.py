import os
from dotenv import load_dotenv
from openai import OpenAI
from utils import encode_image, resize_image


load_dotenv()
client = OpenAI(api_key=os.environ.get('OPENAI_API'))


def calc_nutritional_info_from_image(image_path):
    """
    Calculate nutritional information from image
    """
    with open('text/calc_nutritional_prompt.txt', 'r', encoding='utf-8') as file:
        prompt = file.read()
    
    resized_image_data = resize_image(image_path)
    base64_image = encode_image(resized_image_data)

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


def create_sql_query(user_id, current_time, input_text):
    """
    Create SQL query
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a handsome gym trainer. You gently help your clients lose weight."},
            {"role": "user", "content": [
                {"type": "text", "text": """
                    Given the data shown in #[data], 
                    read the values of calories, protein, fat, carbohydrates, and dietary fiber from the Total Nutritional Information per Serving. 
                    Then, generate an SQL insert statement in the format shown in #[sql].\n\n

                    #[data]\n
                    User ID: {user_id}\n
                    Current time: {current_time}\n
                    Input text: {input_text}\n\n
                 
                    #[sql]\n
                    ```sql
                    INSERT INTO nutritional_records (user_id, date_time, calories, protein, fat, carbohydrates, dietary_fiber) VALUES (1, '2024-07-07 12:00:00', 500, 20, 15, 50, 5);\n
                    ```
                """.format(user_id=user_id, current_time=current_time, input_text=input_text)}
            ]}
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content