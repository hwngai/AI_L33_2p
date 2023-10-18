import pandas as pd
import requests
from datetime import datetime, timedelta
import joblib
from keras.models import load_model
import numpy as np
import random

proxy_file = "model/Webshare 20 proxies.txt"

models = {
    'bigSmall': None,
    'oddEven': None
}

encoder_scaler = None


def make_request_with_random_proxy(url, proxy_file):
    with open(proxy_file, "r") as file:
        proxies = file.readlines()
        
    proxy = random.choice(proxies)
    proxy = proxy.strip().split(":")
    proxy_address = proxy[0]
    proxy_port = proxy[1]
    proxy_username = proxy[2]
    proxy_password = proxy[3]
    
    proxies = {
        'http': f'http://{proxy_username}:{proxy_password}@{proxy_address}:{proxy_port}'
    }
    
    try:
        response = requests.get(url, proxies=proxies)
        if response.status_code == 200:
            return response
        else:
            print("Yêu cầu không thành công. Mã trạng thái:", response.status_code)
    except requests.exceptions.RequestException as e:
        print("Lỗi kết nối:", e)

def crawl_data(max_pages=10000):
    df = pd.DataFrame(columns=["issue", "open_numbers", "encoded_time", "open_numbers_formatted", "sum_total", "sum_big_small", "sum_odd_even"])
    
    for page in range(1, max_pages+1):
        url = f"https://l3377.com/server/lottery/drawResult?lottery_id=49&page={page}&limit=50&date="
        response = make_request_with_random_proxy(url, proxy_file)
        if response.status_code == 200:
            data = response.json()
            draws = data["data"]["list"]
            list_of_dicts = []
            for draw in draws:
                sum_total = draw["open_result"]["sumTotalList"]["sumTotal"]

                if int(draw["open_numbers_formatted"][-1]) % 2 == 0:
                    sum_odd_even = "Even"
                elif int(draw["open_numbers_formatted"][-1]) % 2 == 1:
                    sum_odd_even = "Odd"

                if int(draw["open_numbers_formatted"][-2]) >= 5:
                    sum_big_small = "Big"
                elif int(draw["open_numbers_formatted"][-2]) < 5:
                    sum_big_small = "Small"

                draw_dict = {
                    "issue": draw["issue"],
                    "open_numbers": draw["open_numbers"],
                    "encoded_time": draw["encoded_time"],
                    "open_numbers_formatted": draw["open_numbers_formatted"],
                    "sum_total": sum_total,
                    "sum_big_small": sum_big_small,
                    "sum_odd_even": sum_odd_even
                }
                list_of_dicts.append(draw_dict)
            df = pd.DataFrame(list_of_dicts, columns=["issue", "open_numbers", "encoded_time", "open_numbers_formatted", "sum_total", "sum_big_small", "sum_odd_even"])
        else:
            break
        
    return df

def get_data(data, encoder_scaler):
    selected_columns = ["issue", "encoded_time", "open_numbers_formatted", "sum_big_small", "sum_odd_even"]
    data = data[selected_columns]
    data = data[selected_columns]

    X_bigSmall = []
    Y_bigSmall = []
    X_oddEven = []
    Y_oddEven = []
    issue = []
    encoded_time = []
    for i in range(len(data)):
        if i + 10 > len(data):
            break
        x = []
        for j in range(0, 10):
            value = data['open_numbers_formatted'].loc[i + j]
            if isinstance(value, list):
                x.append([int(val) for val in value])
            else:
                pass
        X_oddEven.append(x)
        X_bigSmall.append(x)
        Y_oddEven.append(data['sum_odd_even'].loc[i])
        Y_bigSmall.append(data['sum_big_small'].loc[i])
        issue.append(data['issue'].loc[i])
        encoded_time.append(data['encoded_time'].loc[i])

    x = np.array(X_oddEven)
    oddEven = Y_oddEven
    bigSmall = Y_bigSmall

    x = x.reshape(-1, 10 * 5)
    x = encoder_scaler.transform(x)

    return x, issue, encoded_time, oddEven, bigSmall

def load_model_and_encoder():
    global models, encoder_scaler

    if models['oddEven'] is None:
        models['oddEven'] = load_model('model/model_oddEven.h5')
    if models['bigSmall'] is None:
        models['bigSmall'] = load_model('model/model_bigSmall.h5')
    if encoder_scaler is None:
        encoder_scaler = joblib.load("model/encoder_scaler.save")

def predict_with_threshold(model, x, threshold=0.5):
    y_pred_prob = model.predict(x)

    y_pred_binary = (y_pred_prob >= threshold).astype(int)

    return y_pred_binary

def calculate_AI_predict(row, target_col):
    ai_pred_col = 'ai_predict_' + target_col
    wrong_ai_col = 'wrong_ai_' + target_col

    if row[wrong_ai_col] < 2:
        return row[ai_pred_col]
    else:
        if target_col == 'bigSmall':
            return 'Small' if row[ai_pred_col] == 'Big' else 'Big'
        elif target_col == 'oddEven':
            return 'Even' if row[ai_pred_col] == 'Odd' else 'Odd'


def calculate_wrong(df, target_col):
    df = df.sort_values(by='issue', ascending=True)
    df = df.reset_index(drop=True)

    df['wrong_ai_' + target_col] = 0
    for i in range(1, len(df)):
        if df.at[i, target_col] != df.at[i - 1, 'ai_predict_' + target_col]:
            df.at[i, 'wrong_ai_' + target_col] = df.at[i - 1, 'wrong_ai_' + target_col] + 1
        else:
            df.at[i, 'wrong_ai_' + target_col] = 0

    df['correction_predict_' + target_col] = df.apply(lambda row: calculate_AI_predict(row, target_col), axis=1)

    df['wrong_correction_' + target_col] = 0

    for i in range(1, len(df)):
        if df.at[i, target_col] != df.at[i - 1, 'correction_predict_' + target_col]:
            df.at[i, 'wrong_correction_' + target_col] = df.at[i - 1, 'wrong_correction_' + target_col] + 1
        else:
            df.at[i, 'wrong_correction_' + target_col] = 0

    df = df.sort_values(by='issue', ascending=False)
    df = df.reset_index(drop=True)

    return df

def predict_l33():
    load_model_and_encoder()
    data = crawl_data(max_pages=1)
    issue = int(data['issue'].iloc[0]) + 1

    encoded_time = data['encoded_time'].iloc[0]
    datetime_obj = datetime.strptime(encoded_time, "%d/%m/%Y %H:%M:%S")
    new_datetime = datetime_obj + timedelta(minutes=2)
    new_encoded_time = new_datetime.strftime("%Y-%m-%d %H:%M:%S")

    x, issues, encoded_times, oddEven, bigSmall = get_data(data,  encoder_scaler)
    y_pred_oddEven = predict_with_threshold(models['oddEven'] , x, threshold=0.489)
    y_pred_bigSmall = predict_with_threshold(models['bigSmall'] , x, threshold=0.492)

    df = pd.DataFrame({
        'issue': issues,
        'encoded_time': encoded_times,
        'bigSmall': bigSmall,
        'oddEven': oddEven,
        'ai_predict_bigSmall': ["Big" if pred == 1 else 'Small' for pred in y_pred_bigSmall],
        'ai_predict_oddEven': ["Even" if pred == 1 else 'Odd' for pred in y_pred_oddEven]
    })


    df = calculate_wrong(df, 'bigSmall')
    df = calculate_wrong(df, 'oddEven')

    return df, new_encoded_time, issue
