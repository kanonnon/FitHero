import os
from datetime import datetime, date
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI
from utils import encode_image, resize_image


load_dotenv()
client = OpenAI(api_key=os.environ.get('OPENAI_API'))

conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()


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


def create_trainer_advice(user_id):
    """
    Create trainer advice
    """
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    end_of_day = datetime.combine(today, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")

    c.execute('SELECT name FROM users WHERE id = ?', (user_id,))
    user_name = c.fetchone()[0]
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
    total_nutrition = (
        f"Calories: {total_nutrition[0]:.2f} kcal\n"
        f"Protein: {total_nutrition[1]:.2f} g\n"
        f"Fat: {total_nutrition[2]:.2f} g\n"
        f"Carbohydrates: {total_nutrition[3]:.2f} g\n"
        f"Dietary Fiber: {total_nutrition[4]:.2f} g"
    )
    c.execute('SELECT target_calories FROM users WHERE id = ?', (user_id,))
    target_calories = c.fetchone()[0]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a handsome gym trainer. You gently help your clients lose weight."},
            {"role": "user", "content": [
                {"type": "text", "text": """
                    Your client, {user_name}, has a daily calorie intake goal of {target_calories} kcal. 
                    Today's calorie intake was as follows:
                    {total_nutrition}
                    Please compare the target calorie intake with the actual intake and generate an advisory message. 
                    Be sure to encourage them gently and kindly. Use emojis appropriately to create a message that will motivate them to keep trying.
                    Please surround the generated message with #[start] and #[end].
                """.format(user_name=user_name, target_calories=target_calories, total_nutrition=total_nutrition)}
            ]}
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content