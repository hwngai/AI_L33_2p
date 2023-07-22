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
            # Xử lý nội dung phản hồi
            print(response.content)
            return response
        else:
            print("Yêu cầu không thành công. Mã trạng thái:", response.status_code)
    except requests.exceptions.RequestException as e:
        print("Lỗi kết nối:", e)
        

def crawl_data(max_pages=10000):
    df = pd.DataFrame(columns=["issue", "open_numbers", "encoded_time", "open_numbers_formatted", "sum_total", "sum_big_small", "sum_odd_even"])
    
    for page in range(1, max_pages+1):
        url = f"https://l33.net/server/lottery/drawResult?lottery_id=49&page={page}&limit=50&date="
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
    selected_columns = ["issue", "open_numbers_formatted", "sum_big_small", "sum_odd_even"]
    data = data[selected_columns]

    X_bigSmall = []
    Y_bigSmall = []
    X_oddEven = []
    Y_oddEven = []
    for i in range(len(data)):
        if i + 10 > len(data):
            break
        x = []
        for j in range(0, 10):
            value = data['open_numbers_formatted'].loc[i + j]
            if isinstance(value, list):
                x.append([int(val) for val in value])
            else:
                print(value, type(value))
        X_oddEven.append(x)
        X_bigSmall.append(x)
        Y_oddEven.append(data['sum_odd_even'].loc[i])
        Y_bigSmall.append(data['sum_big_small'].loc[i])

    x = np.array(X_oddEven)
    y_oddEven = np.array(Y_oddEven[:-1])
    y_bigSmall = np.array(Y_bigSmall[:-1])


    y_true_oddEven = np.where(y_oddEven == 'Even', 0, 1)
    y_true_bigSmall = np.where(y_bigSmall == 'Small', 0, 1)
    x = x.reshape(-1, 10 * 5)
    x = encoder_scaler.transform(x)

    return x, y_true_oddEven, y_true_bigSmall

def load_model_and_encoder():
    global models, encoder_scaler

    if models['oddEven'] is None:
        models['oddEven'] = load_model('model/model_oddEven_2p.h5')
    if models['bigSmall'] is None:
        models['bigSmall'] = load_model('model/model_bigSmall_2p.h5')
    if encoder_scaler is None:
        encoder_scaler = joblib.load("model/encoder_scaler.save")


def predict_with_threshold(model, x, threshold=0.5):
    # Dự đoán xác suất
    y_pred_prob = model.predict(x)

    # Chuyển đổi thành dự đoán nhị phân
    y_pred_binary = (y_pred_prob >= threshold).astype(int)

    return y_pred_binary

def predict_big_small():
    load_model_and_encoder()
    data = crawl_data(max_pages=1)
    issue = int(data['issue'].iloc[0]) + 1

    encoded_time = data['encoded_time'].iloc[0]
    datetime_obj = datetime.strptime(encoded_time, "%Y-%m-%d %H:%M:%S")
    new_datetime = datetime_obj + timedelta(minutes=5)
    new_encoded_time = new_datetime.strftime("%Y-%m-%d %H:%M:%S")
    print(new_encoded_time)

    x, y_true_oddEven, y_true_bigSmall = get_data(data,  encoder_scaler)
    y_pred_oddEven = predict_with_threshold(models['oddEven'] , x, threshold=0.515)
    y_pred_bigSmall = predict_with_threshold(models['bigSmall'] , x, threshold=0.50)


    return y_pred_bigSmall, y_true_bigSmall, y_pred_oddEven, y_true_oddEven, new_encoded_time, issue