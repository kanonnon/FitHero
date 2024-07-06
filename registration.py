import sqlite3
from linebot.models import TextSendMessage


conn = sqlite3.connect('database.db', check_same_thread=False)
c = conn.cursor()


def calculate_maintenance_calories(gender, age, height, weight):
    """
    Calculate basal metabolic rate (BMR) and maintenance calories
    """
    if gender == 'M':
        bmr = 13.397 * weight + 4.799 * height - 5.677 * age + 88.362
    else:
        bmr = 9.247 * weight + 3.098 * height - 4.33 * age + 447.593
    
    maintenance_calories = {
        "Little to no exercise": bmr * 1.2,
        "Light exercise (1-2 days/week)": bmr * 1.375,
        "Moderate exercise (3-4 days/week)": bmr * 1.55,
        "Heavy exercise (4-5 days/week)": bmr * 1.725,
        "Very heavy exercise (6-7 days/week)": bmr * 1.9
    }
    
    return bmr, maintenance_calories


def initiate_user_registration(user_id, reply_token, line_bot_api):
    """
    Initiate user registration
    """
    c.execute('INSERT OR IGNORE INTO users (user_id, state) VALUES (?, ?)', (user_id, 'ASK_NAME'))
    conn.commit()
    line_bot_api.reply_message(
        reply_token, TextSendMessage(text="Hello! Please tell me your name.")
    )


def handle_user_registration(user_id, text, reply_token, line_bot_api):
    """
    Handle user registration process
    """
    c.execute('SELECT state FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()

    if user:
        state = user[0]

        if state == 'ASK_NAME':
            c.execute('UPDATE users SET name = ?, state = ? WHERE user_id = ?', (text, 'ASK_AGE', user_id))
            conn.commit()
            line_bot_api.reply_message(
                reply_token, TextSendMessage(text="Thank you! What is your age? Please answer using numbers only.")
            )
        elif state == 'ASK_AGE':
            try:
                age = int(text)
                if age <= 0:
                    raise ValueError("Age must be a positive integer.")
                c.execute('UPDATE users SET age = ?, state = ? WHERE user_id = ?', (age, 'ASK_GENDER', user_id))
                conn.commit()
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Thank you! What is your gender? Please answer 'M' for male or 'F' for female.")
                )
            except ValueError:
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Invalid input. Please enter a valid age as a positive integer.")
                )
        elif state == 'ASK_GENDER':
            gender = text.strip().upper()
            if gender not in ['M', 'F']:
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Invalid input. Please enter 'M' for male or 'F' for female.")
                )
            else:
                c.execute('UPDATE users SET gender = ?, state = ? WHERE user_id = ?', (gender, 'ASK_HEIGHT', user_id))
                conn.commit()
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Thank you! What is your height (in cm)? Please answer using numbers only.")
                )
        elif state == 'ASK_HEIGHT':
            try:
                height = float(text)
                if height <= 0:
                    raise ValueError("Height must be a positive number.")
                c.execute('UPDATE users SET height = ?, state = ? WHERE user_id = ?', (height, 'ASK_CURRENT_WEIGHT', user_id))
                conn.commit()
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Thank you! What is your current weight (in kg)? Please answer using numbers only.")
                )
            except ValueError:
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Invalid input. Please enter a valid height as a positive number.")
                )
        elif state == 'ASK_CURRENT_WEIGHT':
            try:
                current_weight = float(text)
                if current_weight <= 0:
                    raise ValueError("Weight must be a positive number.")
                c.execute('UPDATE users SET current_weight = ?, state = ? WHERE user_id = ?', (current_weight, 'ASK_TARGET_CALORIES', user_id))
                conn.commit()
                
                c.execute('SELECT age, gender, height, current_weight FROM users WHERE user_id = ?', (user_id,))
                user_data = c.fetchone()
                age, gender, height, weight = user_data

                bmr, maintenance_calories = calculate_maintenance_calories(gender, age, height, weight)
                
                calorie_message = (
                    f"Thank you! Now let's set your daily target calorie intake.\n"
                    f"Below are estimates of your total daily calorie expenditure, which you can use to set your target intake.\n\n"
                    f"Basal Metabolic Rate (BMR): {bmr:.2f} kcal/day\n\n"
                    f"Estimates of your total daily calorie expenditure:\n"
                    f"Little to no exercise: {maintenance_calories['Little to no exercise']:.2f} kcal/day\n"
                    f"Light exercise (1-2 days/week): {maintenance_calories['Light exercise (1-2 days/week)']:.2f} kcal/day\n"
                    f"Moderate exercise (3-4 days/week): {maintenance_calories['Moderate exercise (3-4 days/week)']:.2f} kcal/day\n"
                    f"Heavy exercise (4-5 days/week): {maintenance_calories['Heavy exercise (4-5 days/week)']:.2f} kcal/day\n"
                    f"Very heavy exercise (6-7 days/week): {maintenance_calories['Very heavy exercise (6-7 days/week)']:.2f} kcal/day\n\n"
                    f"What is your target daily calorie intake? Please answer using numbers only."
                )
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text=calorie_message)
                )
            except ValueError:
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Invalid input. Please enter a valid weight as a positive number.")
                )
        elif state == 'ASK_TARGET_CALORIES':
            try:
                target_calories = int(text)
                if target_calories <= 0:
                    raise ValueError("Target calories must be a positive integer.")
                c.execute('UPDATE users SET target_calories = ?, state = ? WHERE user_id = ?', (target_calories, 'REGISTERED', user_id))
                conn.commit()
                with open('text/app_explanation.txt', 'r', encoding='utf-8') as file:
                    explanation = file.read()
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text=f"Registration complete!\n{explanation}")
                )
            except ValueError:
                line_bot_api.reply_message(
                    reply_token, TextSendMessage(text="Invalid input. Please enter a valid target daily calorie intake as a positive integer.")
                )
    else:
        line_bot_api.reply_message(
            reply_token, TextSendMessage(text="You are already registered!")
        )
