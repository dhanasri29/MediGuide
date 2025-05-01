from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, ChatHistory
from forms import SignupForm, LoginForm
from config import Config
import pandas as pd
from werkzeug.utils import secure_filename
import numpy as np
from tensorflow.keras.models import load_model
import pickle
from tensorflow.keras.preprocessing import image
import os
from datetime import datetime
from flask_wtf import CSRFProtect

#App initialization
app = Flask(__name__)
app.config.from_object(Config)

# Folder for uploaded images
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load the trained models
MODEL_PATH_1 = 'skin_disease_model.h5'
model_1 = load_model(MODEL_PATH_1)

# Update class names based on folder structure used in training
CLASS_NAMES_1 = ['Acne', 'Atopic', 'Basal cell carcinoma']  
disease_info = {
    "Acne": {
        "Description": "Acne is a skin condition where pores get clogged, leading to pimples and blackheads.",
        "Precautions": ["Avoid touching face", "Use non-comedogenic products", "Cleanse regularly"],
        "Medications": ['Benzoyl peroxide', 'Topical retinoids', 'Oral antibiotics', 'Isotretinoin'],
        "Diet": ['Low-glycemic foods', 'Omega-3s', 'Probiotics', 'Fruits and Vegetables'],
        "Recommendations": "Follow a low-glycemic and anti-inflammatory diet"
    },
    "Atopic": {
        "Description": "Atopic dermatitis (eczema) is a chronic skin condition causing dry, itchy, inflamed skin.",
        "Precautions": ["Moisturize often", "Use mild cleansers", "Avoid allergens"],
        "Medications": ['Topical steroids', 'Calcineurin inhibitors', 'Antihistamines'],
        "Diet": ['Anti-inflammatory foods', 'Omega-3s', 'Vitamin D', 'Probiotics'],
        "Recommendations": "Moisturize regularly and avoid triggers"
    },
    "Basal cell carcinoma": {
        "Description": "BCC is a common skin cancer that appears as a small, shiny bump, usually from sun damage.",
        "Precautions": ["Avoid sun exposure", "Use sunscreen", "Wear protective clothing"],
        "Medications": ['5-FU cream', 'Imiquimod', 'Surgical excision', 'Mohs surgery'],
        "Diet": ['Beta-carotene foods', 'Antioxidants', 'Omega-3s', 'Whole grains'],
        "Recommendations": "Protect skin from sun and eat antioxidant-rich foods"
    }
}


# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login_route'  # Redirect to login page if not authenticated
csrf = CSRFProtect(app)

# Load the trained model and label encoder
with open('nn_model.pkl', 'rb') as f:
    model = pickle.load(f)

with open('label_encoder.pkl', 'rb') as f:
    label_encoder = pickle.load(f)

# Load additional data for disease details
precautions = pd.read_csv('precautions_data.csv')
description = pd.read_csv('description.csv')
medications = pd.read_csv('medications.csv')
diets = pd.read_csv('diets.csv')
workout = pd.read_csv('workout_df.csv')

# Load Training.csv to get symptom columns
training_data = pd.read_csv('Training.csv')
symptoms = training_data.columns[:-1]  # Exclude target column 'prognosis'
symptom_dict = {symptom: idx for idx, symptom in enumerate(symptoms)}

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper functions
#Retrieves detailed information about a disease, including description, precautions, medications, diet, and workout plan.
def helper(disease):
    desc = description[description['Disease'] == disease]['Description'].iloc[0]
    precautions_list = precautions.loc[precautions['Disease'] == disease].iloc[:, 1:].values.flatten().tolist()
    precautions_list = [p for p in precautions_list if pd.notna(p)]
    meds = medications[medications['Disease'] == disease]['Medication'].tolist()
    diet = diets[diets['Disease'] == disease]['Diet'].tolist()
    workout_plan = workout[workout['disease'] == disease]['workout'].iloc[0]
    return desc, precautions_list, meds, diet, workout_plan

# Routes

# Home Page Route (Public)
@app.route('/')
def home():
    return render_template('home.html')

# Chatbot Interface Route 
@app.route('/chat')
@login_required
def chat():
   return render_template('index.html')


# Chatbot Interface Route 
@app.route('/upload')
@login_required
def upload():
    return render_template('upload.html')



@csrf.exempt
@app.route('/upload1', methods=['POST'])
@login_required
def upload1():
    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('upload.html', prediction="No file uploaded or selected.", image_path=None)

    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    img = image.load_img(filepath, target_size=(150, 150))
    img_array = image.img_to_array(img)
    img_array = img_array.astype('float32') 
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    predictions = model_1.predict(img_array)
    predicted_class = CLASS_NAMES_1[np.argmax(predictions[0])]
    confidence = round(np.max(predictions[0]) * 100, 2)

    # Get detailed info
    disease_details = disease_info.get(predicted_class)

    return render_template('upload.html',
                           prediction=f"{predicted_class}",
                           image_path=f"/static/uploads/{filename}",
                           disease_details=disease_details)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = SignupForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, is_admin=False)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('login_route'))
    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login_route():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login_route'))
        login_user(user, remember=form.remember_me.data)
        flash('Logged in successfully.', 'success')
        # Check if the user is an admin
        if user.is_admin:
            return redirect(url_for('admin'))  # Redirect to admin page
        else:
            return redirect(url_for('chat'))  # Redirect to chat page for regular users
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('You do not have access to this page.', 'danger')
        return redirect(url_for('home'))
    users = User.query.all()
    chats = ChatHistory.query.order_by(ChatHistory.timestamp.desc()).all()
    return render_template('admin.html', users=users, chats=chats)

# API Endpoints -- an API endpoint is a specific location within an API that accepts requests and sends back responses.
@app.route('/predict', methods=['POST'])
@login_required
@csrf.exempt 

#Accepts symptoms, predicts a disease using the model, and saves chat history.

def predict():
    data = request.json
    user_symptoms = data.get('symptoms', [])

    # Backend Validation: Check if at least 3 symptoms are provided
    if len(user_symptoms) < 3:
        return jsonify({'error': 'Please provide at least three symptoms.'}), 400

    # Initialize input data
    input_data = [0] * len(symptom_dict)
    for symptom in user_symptoms:
        index = symptom_dict.get(symptom.lower())
        if index is not None:
            input_data[index] = 1

    # Create DataFrame for prediction
    input_df = pd.DataFrame([input_data])

    # Predict disease
    predicted = model.predict(input_df)
    predicted_disease = label_encoder.inverse_transform(predicted)[0]

    # Store chat history
    chat = ChatHistory(
        user_id=current_user.id,
        symptom_input=", ".join(user_symptoms),
        disease_predicted=predicted_disease
    )
    db.session.add(chat)
    db.session.commit()

    return jsonify({'disease': predicted_disease, 'chat_id': chat.id})

@app.route('/details', methods=['POST'])
@login_required
@csrf.exempt  
def get_details():
    data = request.json
    disease = data.get('disease')
    chat_id = data.get('chat_id')
    detail_key = data.get('detail_key')  # The detail being viewed

    if not disease or not chat_id:
        return jsonify({'error': 'Missing disease or chat_id.'}), 400

    try:
        desc, precautions_list, meds, diet, workout_plan = helper(disease)
    except IndexError:
        return jsonify({'error': 'Disease details not found.'}), 404

    # Update chat history with details viewed
    chat = ChatHistory.query.get(chat_id)
    if chat:
        if not chat.details_viewed:
            chat.details_viewed = detail_key
        else:
            if detail_key not in chat.details_viewed.split(', '):
                chat.details_viewed += f", {detail_key}"
        db.session.commit()

    details = {
        'description': desc,
        'precautions': precautions_list,
        'medications': meds,
        'diet': diet,
        'workout': workout_plan
    }

    return jsonify(details)

 ##Create an initial admin user if none exists
#@app.before_first_request
#def create_tables():
#   db.create_all()
#  if not User.query.filter_by(username='admin').first():
#         admin_user = User(username='admin', email='admin@example.com', is_admin=True)
#         admin_user.set_password('adminpassword')  # Change to a secure password
#        db.session.add(admin_user)
#         db.session.commit()
#        print('Created initial admin user.')

if __name__ == '__main__':
    app.run(debug=True)
