from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
import qrcode
import os
from datetime import datetime
import hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ff-likes-super-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# UPI Payment Details
UPI_ID = "mmahendra@fam"
UPI_NAME = "Akshay"

# Admin Credentials
ADMIN_USERNAME = "mahi"
ADMIN_PASSWORD = "mahi"

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    credits = db.Column(db.Integer, default=0)
    is_premium = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    product = db.Column(db.String(100), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(20), default='pending')
    screenshot = db.Column(db.String(200))
    verified_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='payments')

class LikeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uid = db.Column(db.String(50), nullable=False)
    region = db.Column(db.String(20), nullable=False)
    credits_used = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='pending')
    response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='like_requests')

# Create tables
with app.app_context():
    db.create_all()

def hash_password(password):
    return generate_password_hash(password)

def verify_password(password, hash):
    return check_password_hash(hash, password)

def generate_transaction_id():
    return secrets.token_hex(8).upper()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            credits=50  # Welcome bonus
        )
        db.session.add(user)
        db.session.commit()
        flash('Account created! Welcome bonus 50 credits added.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and verify_password(password, user.password_hash):
            session['user_id'] = user.id
            session['username'] = user.username
            session['credits'] = user.credits
            flash(f'Welcome back {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    payments = Payment.query.filter_by(user_id=user.id).order_by(Payment.created_at.desc()).limit(5).all()
    requests = LikeRequest.query.filter_by(user_id=user.id).order_by(LikeRequest.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', user=user, payments=payments, requests=requests)

@app.route('/buy-credits', methods=['GET', 'POST'])
def buy_credits():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    products = {
        'basic': {'name': 'Basic Pack', 'credits': 100, 'price': 99, 'desc': '100 Credits'},
        'pro': {'name': 'Pro Pack', 'credits': 500, 'price': 399, 'desc': '500 Credits'},
        'elite': {'name': 'Elite Pack', 'credits': 1500, 'price': 999, 'desc': '1500 Credits + Premium'},
        'ultimate': {'name': 'Ultimate Pack', 'credits': 5000, 'price': 2999, 'desc': '5000 Credits + Lifetime Premium'}
    }
    
    if request.method == 'POST':
        product = request.form['product']
        if product in products:
            user = User.query.get(session['user_id'])
            transaction_id = generate_transaction_id()
            
            payment = Payment(
                user_id=user.id,
                amount=products[product]['price'],
                product=products[product]['name'],
                transaction_id=transaction_id
            )
            db.session.add(payment)
            db.session.commit()
            
            # Generate QR Code
            qr_data = f"pay?pa={UPI_ID}&pn={UPI_NAME}&am={products[product]['price']}&cu=INR"
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_path = f"static/qr_codes/{transaction_id}.png"
            os.makedirs(os.path.dirname(qr_path), exist_ok=True)
            img.save(qr_path)
            
            flash(f'Payment created! Transaction ID: {transaction_id}', 'success')
            return render_template('buy_credits.html', products=products, payment=payment, qr_path=qr_path)
    
    return render_template('buy_credits.html', products=products)

@app.route('/send-likes', methods=['POST'])
def send_likes():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    uid = data['uid']
    region = data['region']
    
    user = User.query.get(session['user_id'])
    if user.credits < 1:
        return jsonify({'error': 'Insufficient credits'}), 400
    
    # Call your API
    import requests
    api_url = f"https://mahi-api-like.vercel.app/like?uid={uid}&server_name={region}"
    
    try:
        response = requests.get(api_url, timeout=10)
        api_data = response.json()
        
        # Deduct credits
        user.credits -= 1
        db.session.commit()
        session['credits'] = user.credits
        
        # Save request
        like_request = LikeRequest(
            user_id=user.id,
            uid=uid,
            region=region,
            response=str(api_data)
        )
        db.session.add(like_request)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'credits': user.credits,
            'response': api_data,
            'message': 'Likes sent successfully!' if api_data.get('likes', 0) > 0 else 'Max likes reached'
        })
    
    except Exception as e:
        return jsonify({'error': 'API Error'}), 500

@app.route('/admin')
def admin():
    if session.get('username') != ADMIN_USERNAME or session.get('admin_logged_in') != True:
        return redirect(url_for('admin_login'))
    
    users = User.query.all()
    pending_payments = Payment.query.filter_by(status='pending').all()
    all_payments = Payment.query.order_by(Payment.created_at.desc()).limit(20).all()
    
    return render_template('admin.html', 
                         users=users, 
                         pending_payments=pending_payments,
                         all_payments=all_payments)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['username'] = username
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        
        flash('Invalid admin credentials!', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/verify-payment/<int:payment_id>')
def verify_payment(payment_id):
    if session.get('admin_logged_in') != True:
        return redirect(url_for('admin_login'))
    
    payment = Payment.query.get(payment_id)
    if payment and payment.status == 'pending':
        user = User.query.get(payment.user_id)
        
        # Add credits based on product
        if 'Basic' in payment.product:
            user.credits += 100
        elif 'Pro' in payment.product:
            user.credits += 500
        elif 'Elite' in payment.product:
            user.credits += 1500
            user.is_premium = True
        elif 'Ultimate' in payment.product:
            user.credits += 5000
            user.is_premium = True
        
        payment.status = 'verified'
        db.session.commit()
        
        flash(f'Payment verified! {user.username} received credits.', 'success')
    
    return redirect(url_for('admin'))

@app.route('/api/user-stats')
def user_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.get(session['user_id'])
    return jsonify({
        'credits': user.credits,
        'is_premium': user.is_premium,
        'username': user.username
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
