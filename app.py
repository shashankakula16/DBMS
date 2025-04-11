import streamlit as st
import sqlite3
import hashlib
import pandas as pd
import altair as alt
import plotly.graph_objects as go

# --- DATABASE SETUP ---
def create_tables():
    conn = sqlite3.connect('health.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS health_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            name TEXT,
            gender TEXT,
            goal TEXT,
            age INTEGER,
            weight REAL,
            height REAL,
            blood_pressure TEXT,
            bmi REAL,
            steps_recommended INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add missing columns if not already in the table
    try:
        c.execute("ALTER TABLE health_data ADD COLUMN gender TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE health_data ADD COLUMN goal TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    conn = sqlite3.connect('health.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('health.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hash_password(password)))
    data = c.fetchone()
    conn.close()
    return data

def insert_health_data(username, name, gender, goal, age, weight, height, bp, bmi, steps):
    conn = sqlite3.connect('health.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO health_data (username, name, gender, goal, age, weight, height, blood_pressure, bmi, steps_recommended)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (username, name, gender, goal, age, weight, height, bp, bmi, steps))
    conn.commit()
    conn.close()

def get_user_data_df(username):
    conn = sqlite3.connect('health.db')
    df = pd.read_sql_query("SELECT timestamp, name, gender, goal, age, weight, height, bmi, steps_recommended FROM health_data WHERE username = ?", conn, params=(username,))
    conn.close()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

# --- BMI + STEPS LOGIC ---
def calculate_bmi(weight, height_cm):
    height_m = height_cm / 100
    return round(weight / (height_m ** 2), 2)

def recommend_steps(weight, height, age, gender, goal):
    base = 6000
    factor = 1
    if gender == "Male":
        factor += 0.1
    elif gender == "Female":
        factor += 0.05

    if goal == "Weight Loss":
        base += 2000
    elif goal == "Muscle Building":
        base += 1000
    elif goal == "Weight Gain":
        base += 500

    return int(base * factor)

def interpret_bmi(bmi):
    if bmi < 18.5:
        return "Underweight (Ideal: 18.5 - 24.9)"
    elif 18.5 <= bmi <= 24.9:
        return "Normal (Ideal)"
    elif 25 <= bmi <= 29.9:
        return "Overweight (Ideal: 18.5 - 24.9)"
    else:
        return "Obese (Ideal: 18.5 - 24.9)"

# --- MAIN APP STARTS HERE ---
create_tables()
st.set_page_config(page_title="Health Monitor", layout="centered", page_icon="💪")
st.title("Body & Health Monitoring System")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""

menu = ["Login", "Register"]

if not st.session_state.logged_in:
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Register":
        st.subheader("Create New Account")
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        confirm_pass = st.text_input("Confirm Password", type="password")
        if st.button("Register"):
            if new_pass != confirm_pass:
                st.error("Passwords do not match.")
            elif register_user(new_user, new_pass):
                st.success("Account created! Go to Login.")
            else:
                st.error("Username already exists.")

    elif choice == "Login":
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Welcome {username}!")
            else:
                st.error("Invalid credentials")
else:
    st.sidebar.success(f"Logged in as {st.session_state.username}")
    action = st.sidebar.radio("Choose Action", ["Dashboard", "Add Health Data", "View Records", "Graph", "Logout"])

    if action == "Dashboard":
        st.subheader("Health Overview")
        df = get_user_data_df(st.session_state.username)
        if not df.empty:
            col1, col2 = st.columns(2)
            col1.metric("Latest BMI", df['bmi'].iloc[-1])
            col1.metric("Avg Steps", int(df['steps_recommended'].mean()))
            col2.metric("Total Records", len(df))
            col2.metric("Last Entry", df['timestamp'].max().strftime('%Y-%m-%d'))
        else:
            st.info("No data available yet.")

    elif action == "Add Health Data":
        st.subheader("Enter Your Health Details")
        name = st.text_input("Full Name")
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        goal = st.selectbox("Your Goal", ["Weight Loss", "Muscle Building", "Weight Gain"])
        age = st.number_input("Age", 0)
        weight = st.number_input("Weight (kg)", 0.0)
        height = st.number_input("Height (cm)", 0.0)
        bp = st.text_input("Blood Pressure (e.g., 120/80)")

        if st.button("Submit"):
            if name and gender and goal and age and weight and height and bp:
                bmi = calculate_bmi(weight, height)
                steps = recommend_steps(weight, height, age, gender, goal)
                insert_health_data(st.session_state.username, name, gender, goal, age, weight, height, bp, bmi, steps)
                st.success(f"Your BMI: {bmi} ({interpret_bmi(bmi)})")
                st.info(f"Recommended Steps: {steps} steps/day")
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = bmi,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "BMI Indicator"},
                    gauge = {
                        'axis': {'range': [None, 40]},
                        'steps': [
                            {'range': [0, 18.5], 'color': "lightblue"},
                            {'range': [18.5, 24.9], 'color': "lightgreen"},
                            {'range': [25, 29.9], 'color': "orange"},
                            {'range': [30, 40], 'color': "red"}
                        ],
                        'threshold': {
                            'line': {'color': "black", 'width': 4},
                            'thickness': 0.75,
                            'value': bmi}
                    }
                ))
                st.plotly_chart(fig)
            else:
                st.warning("Please fill all fields.")

    elif action == "View Records":
        st.subheader("Your Past Health Records")
        df = get_user_data_df(st.session_state.username)
        st.dataframe(df)

    elif action == "Graph":
        st.subheader("BMI Trend Over Time")
        df = get_user_data_df(st.session_state.username)
        if not df.empty:
            chart = alt.Chart(df).mark_line(point=True).encode(
                x='timestamp:T',
                y='bmi:Q',
                tooltip=['timestamp', 'bmi']
            ).properties(width=600, height=400)
            st.altair_chart(chart)
        else:
            st.warning("No records to display.")

    elif action == "Logout":
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.success("You have been logged out.")