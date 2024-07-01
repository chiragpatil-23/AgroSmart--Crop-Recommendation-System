from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LinearRegression
from datetime import datetime
from flask import Flask, render_template, request
import os
import cv2
import requests
from joblib import load

import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__, static_folder='static')

app.secret_key = '5766ghghgg7654dfd7h9hsffh'


@app.route('/')
def home():
    return render_template('landing.html')


## Authentication steps

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':

        name = request.form['name']
        address = request.form['address']
        email = request.form['email']
        contact = request.form['contact']
        age = request.form['age']
        password = request.form['password']
        re_password = request.form['re_password']

        # Check if email already exists in the database
        conn = sqlite3.connect(
            'database/Farmer.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_details WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user is not None:
            # If the user already exists, add a flash message and redirect back to the signup page
            session['message'] = 'email already exist. Please go to login page.'

            return redirect(url_for('signup', error='email already exist.'))

        elif password != re_password:

            session['message'] = 'Both password are different.'

            return redirect(url_for('signup', error='password do not match.'))

        else:
        
            conn = sqlite3.connect(
                'database/Farmer.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO user_details (name, address, email, contact, age, password, re_password) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (name, address, email, contact, age, password, re_password))
            conn.commit()
            conn.close()

            return redirect(url_for('login'))

    elif request.args.get('error') is None:
        return render_template('signup.html')

    else:
        error = request.args.get('error')
        return render_template('signup.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('database/Farmer.db')
        c = conn.cursor()

        c.execute(
            "SELECT * FROM user_details WHERE email = ? AND password = ?", (email, password))
        user = c.fetchone()
        conn.close()

        if user is not None:
            session['email'] = user[1]
            
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password')
    else:
        return render_template('login.html')




## Page Redirect Steps

@app.route('/index')
def index():

    email = session.get('email')
    print(email)
    conn = sqlite3.connect('database/Farmer.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM user_details WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    print(user)


    if 'email' in session:
        return render_template('index.html', current_user=session['email'], user=user[0])
    return redirect(url_for('login'))


@app.route('/contactus', methods=['GET', 'POST'])
def contactus():

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        conn = sqlite3.connect(
            'database/Farmer.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO user_query (name, email, subject, message) VALUES (?, ?, ?, ?)",
                       (name, email, subject, message))
        conn.commit()
        conn.close()

        message = "We have received your response, Our team will contact you shortly."

        return render_template('contactus.html',  message = message)

    return render_template('contactus.html')

@app.route('/logout')
def logout():
    # Clear session data
    session.clear()
    # Redirect to the login page
    return redirect(url_for('login'))



### prediction Steps

### Crop Price
commodity_mapping = {
    'Bajra(Pearl Millet/Cumbu)': "static/bajra.cms",
    'Beans': 'beans.jpg'
}
   

@app.route('/crop_price', methods=['GET', 'POST'])
def crop_price():
    '''
    For rendering results on HTML GUI
    '''
    if request.method == 'POST':
        commodity = request.form['commodity']
        market = request.form['market']
        district = request.form['district']

        date = request.form['date']

        provided_date = datetime.strptime(date, '%Y-%m-%d').date()

        # Get today's date
        today_date = datetime.now().date()

        # Convert today's date to datetime for subtraction
        today_datetime = datetime.combine(today_date, datetime.min.time())

        # Calculate the difference
        date_difference = provided_date - today_datetime.date()

        # Convert the date difference to days
        forecast_steps = date_difference.days

        # Load the crop dataset from local CSV file
        crop_df = pd.read_csv('../dataset/cropPrice.csv', parse_dates=['Price Date'])
        crop_df = crop_df.set_index('Price Date')
        
        # selected_commodity = input("Enter the District name: ")
        selected_df = crop_df[crop_df['District'] == district]

        # selected_commodity = input("Enter the Market name: ")
        selected_df = selected_df[selected_df['Market'] == market]

        # selected_commodity = input("Enter the Commodity name: ")
        selected_df = selected_df[selected_df['Commodity'] == commodity]

        print(selected_df.shape)

        if selected_df.shape[0] == 0:
             message = "Sorry but currently we don't have data for above filters."
             return render_template('crop_price.html', message=message)


        # Extract the target variable
        target = 'Modal Price (Rs./Quintal)'
        data = selected_df[target].values.reshape(-1, 1)

        # Normalize the data
        scaler = MinMaxScaler(feature_range=(0, 1))
        data_scaled = scaler.fit_transform(data)

        # Split the data into training and testing sets
        split_index = int(len(data_scaled) * 0.8)
        train = data_scaled[:split_index]
        test = data_scaled[split_index:]

        # Prepare the data for linear regression
        def create_dataset(X, y, time_steps=1):
            Xs, ys = [], []
            for i in range(len(X) - time_steps):
                Xs.append(X[i:(i + time_steps)])
                ys.append(y[i + time_steps])
            return np.array(Xs), np.array(ys)

        time_steps = 30  # Number of time steps to look back
        X_train, y_train = create_dataset(train, train, time_steps)
        X_test, y_test = create_dataset(test, test, time_steps)

        # Flatten X_train and X_test
        X_train = X_train.reshape(X_train.shape[0], -1)
        X_test = X_test.reshape(X_test.shape[0], -1)

        # Fit linear regression model
        model = LinearRegression()
        model.fit(X_train, y_train)

        last_sequence = X_test[-1]
        predicted_prices_future = []

        for _ in range(forecast_steps):
            next_price_scaled = model.predict([last_sequence])[0]
            next_price_scaled = np.reshape(next_price_scaled, (-1, 1))
            next_price = scaler.inverse_transform(next_price_scaled)[0][0]
            predicted_prices_future.append(next_price)
            last_sequence = np.roll(last_sequence, -1)
            last_sequence[-1] = next_price_scaled

        image_url = commodity_mapping.get(commodity)

        print(image_url)

        return render_template('crop_price.html',commodity=commodity, img=image_url, x = provided_date, z = round(predicted_prices_future[forecast_steps-1], 2))
    return render_template('crop_price.html')


# List of major cities in India
indian_cities = [
    "Jaipur", "Mumbai", "Delhi", "Kolkata", "Chennai", 
    "Bangalore", "Hyderabad", "Pune", "Ahmedabad", "Surat", 
    "Lucknow", "Nagpur", "Indore", "Bhopal", "Patna", "Sangli",
    "Vadodara", "Ghaziabad", "Ludhiana", "Agra", "Varanasi",
    "Ranchi", "Kanpur", "Nashik", "Coimbatore", "Kochi", 
    "Visakhapatnam", "Thiruvananthapuram", "Amritsar", "Vijayawada", "Guwahati", 
    "Navi Mumbai", "Thane", "Bhubaneswar", "Dehradun", "Bikaner", 
    "Jodhpur", "Rajkot", "Shimla", "Srinagar", "Jammu"
]


@app.route('/weather', methods=['GET', 'POST'])
def weather():
    if request.method == 'POST':

        temperature_celsius = None
        weather_condition = None
        
        city_name = request.form['city']
        date = request.form['date']

        provided_date = datetime.strptime(date, '%Y-%m-%d').date()

        # Get today's date
        today_date = datetime.now().date()

        # Convert today's date to datetime for subtraction
        today_datetime = datetime.combine(today_date, datetime.min.time())

        # Calculate the difference
        date_difference = provided_date - today_datetime.date()

        # Convert the date difference to days
        n_days = date_difference.days
   
        # API endpoint URL
        url = "http://api.weatherapi.com/v1/forecast.json"

        # Validate user input
        print(city_name)
        print("----------------------------------")
        # if city_name.lower() in indian_cities.lower():
        if city_name.lower() in [city.lower() for city in indian_cities]:
            
            try:
                n_days = int(n_days)
                if n_days < 1:
                    raise ValueError("Please enter a positive integer value for the number of days.")
            except ValueError as e:
                print("Invalid input:", e)
            else:
                # Parameters
                params = {
                    "key": "627b10c8fa8b4ff28c190325242904",
                    "q": city_name + ", India",  # Specify the selected city name and country
                    "days": n_days + 1,  # Retrieve forecast data for n_days plus 1 to get the forecast for after n_days
                    "aqi": "no"  # Exclude air quality data if not needed
                }

                # Send GET request to the API
                response = requests.get(url, params=params)

                # Check if request was successful (status code 200)
                if response.status_code == 200:
                    # Parse JSON response
                    data = response.json()
                    
                    # Extract forecast data for after n_days
                    forecast_after_n_days = data['forecast']['forecastday'][n_days]

                    # Extract relevant weather information
                    date = forecast_after_n_days['date']
                    temperature_celsius = forecast_after_n_days['day']['avgtemp_c']
                    weather_condition = forecast_after_n_days['day']['condition']['text']

                    # Print the weather information for after n_days
                    print(f'\nWeather forecast for {city_name} after {n_days} days ({date}):')
                    print(f'Temperature: {temperature_celsius}°C')
                    print(f'Weather Condition: {weather_condition}')

                    message = f"Weather forecast for {city_name} after {n_days} days i.e, {provided_date}: Temperature: {temperature_celsius}°C, Weather Condition: {weather_condition}"


                    return render_template('weather.html', indian_cities=indian_cities, message = message)
                
                else:
                    print('Error:', response.status_code)

                    return render_template('weather.html', message=response.status_code)
        else:
            print("Invalid city selection. Please enter a valid city name.")
            message = "Invalid city selection. Please enter a valid city name."
            return render_template('weather.html', message = message)

            
    return render_template('weather.html')



### Crop Recommendation

label_mapping = {
            0: 'apple', 1: 'banana', 2: 'blackgram', 3: 'chickpea', 4: 'coconut', 5: 'coffee', 
            6: 'cotton', 7: 'grapes', 8: 'jute', 9: 'kidneybeans', 10: 'lentil', 11: 'maize', 
            12: 'mango', 13: 'mothbeans', 14: 'mungbean', 15: 'muskmelon', 16: 'orange', 
            17: 'papaya', 18: 'pigeonpeas', 19: 'pomegranate', 20: 'rice', 21: 'watermelon'
        }


image_urls = {
    'apple': "static/apple.jpg",
    'banana': 'static/banana.jpg',
    'blackgram': 'static/blackgram.webp',
    'chickpea': 'static/chickpea.jpg',
    'coconut': 'static/coconut.jpg',
    'coffee': 'static/coffee.jpg',
    'cotton': 'static/cotton.jpg',
    'grapes': 'static/grapes.jpg',
    'jute': 'static/jute.jpg',
    'kidneybeans': 'static/kidneybeans.jpg',
    'lentil': 'static/lentil.jpg',
    'maize': 'static/maize.jpg',
    'mango': 'static/mango.jpg',
    'mothbeans': 'static/mothbeans.jpg',
    'mungbean': 'static/mungbean.jpg',
    'muskmelon': 'static/muskmelon.jpg',
    'orange': 'static/orange.jpg',
    'papaya': 'static/papaya.jpg',
    'pigeonpeas': 'static/pigeonpeas.jpg',
    'pomegranate': 'static/pomegranate.jpg',
    'rice': 'static/rice.jpg',
    'watermelon': 'static/watermelon.jpg'
}
    

@app.route('/crop_recommendation', methods=['GET', 'POST'])
def crop_recommendation():
    '''
    For rendering results on HTML GUI
    '''
    if request.method == 'POST':

        nitrogen = request.form['nitrogen']
        phosphorous = request.form['phosphorous']
        potassium = request.form['potassium']
        temperature = request.form['temperature']
        humidity = request.form['humidity']
        ph = request.form['ph']
        rainfall = request.form['rainfall']
        
        loaded_model = load('../models/model.joblib')

        recommended_crop = loaded_model.predict([[nitrogen, phosphorous, potassium, temperature, humidity, ph, rainfall]])

        predicted_label = label_mapping[recommended_crop[0]]


         # Get the image URL based on the predicted label
        image_url = image_urls.get(predicted_label)

        return render_template('crop_recommendation.html', predicted_label=predicted_label, img=image_url)

    return render_template('crop_recommendation.html')

@app.route('/crop_recommendation_default', methods=['GET', 'POST'])
def crop_recommendation_default():
    '''
    For rendering results on HTML GUI
    '''
    predicted_label = None

    if request.method == 'POST':

        nitrogen = request.form['nitrogen']
        phosphorous = request.form['phosphorous']
        potassium = request.form['potassium']
        temperature = request.form['temperature']
        humidity = request.form['humidity']
        ph = request.form['ph']
        rainfall = request.form['rainfall']
        
        loaded_model = load('../models/model.joblib')

        recommended_crop = loaded_model.predict([[nitrogen, phosphorous, potassium, temperature, humidity, ph, rainfall]])

        predicted_label = label_mapping[recommended_crop[0]]

        # Get the image URL based on the predicted label
        image_url = image_urls.get(predicted_label)

        return render_template('crop_recommendation_default.html', predicted_label=predicted_label, img=image_url)
    return render_template('crop_recommendation_default.html')



if __name__ == "__main__":
    app.run(debug=True)
