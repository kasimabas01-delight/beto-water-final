import os
import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'beto_water_super_secret_key_2026_advanced_v3'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///beto_water_v3.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
db.init_app(app)

# ----------------- የዳታቤዝ ሞዴሎች -----------------

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    current_month_name = db.Column(db.String(50), default="ጥቅምት")
    due_date = db.Column(db.String(50), default="2026-10-30")
    office_phone = db.Column(db.String(50), default="0911223344")
    office_address = db.Column(db.String(100), default="በቶ ከተማ፣ ዋናው አስፓልት አጠገብ")
    bank_account = db.Column(db.String(100), default="1000123456789 (CBE)")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='customer') # admin, reader, customer
    phone = db.Column(db.String(20))
    meter_number = db.Column(db.String(50), unique=True, nullable=True)
    previous_reading = db.Column(db.Float, default=0.0)
    current_reading = db.Column(db.Float, default=0.0)
    base_bill = db.Column(db.Float, default=0.0) 
    penalty = db.Column(db.Float, default=0.0)    
    old_debt = db.Column(db.Float, default=0.0)   
    balance = db.Column(db.Float, default=0.0)    
    status = db.Column(db.String(20), default='Paid')

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(100))
    meter_number = db.Column(db.String(50))
    month_name = db.Column(db.String(50), nullable=False)
    prev_reading = db.Column(db.Float, nullable=False)
    curr_reading = db.Column(db.Float, nullable=False)
    consumption = db.Column(db.Float, nullable=False)
    base_amount = db.Column(db.Float, nullable=False)
    penalty_amount = db.Column(db.Float, default=0.0)
    old_debt_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Unpaid')

with app.app_context():
    db.create_all()
    if not SystemConfig.query.first():
        db.session.add(SystemConfig())
    db.session.commit()

# 💰 የደረጃ ታሪፍ ስሌት
def calculate_block_tariff(consumption):
    amount = 0.0
    if consumption <= 10:
        amount = consumption * 15.0
    elif consumption <= 20:
        amount = (10 * 15.0) + ((consumption - 10) * 20.0)
    else:
        amount = (10 * 15.0) + (10 * 20.0) + ((consumption - 20) * 30.0)
    return amount

# ----------------- ROUTES -----------------

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        meter_num = request.form.get('meter_number', '').strip()

        # ✅ የአስተዳዳሪ እና ቆጣሪ አንባቢ ትክክለኛ መግቢያ ፍተሻ
        if username and password:
            if username == 'admin' and password == 'admin@123':
                session.clear()
                session['role'] = 'admin'
                return redirect(url_for('admin_dashboard'))
            elif username == 'reader' and password == 'reader@123':
                session.clear()
                session['role'] = 'reader'
                return redirect(url_for('reader_dashboard'))
            flash('የመግቢያ ስም ወይም የይለፍ ቃል ተሳስቷል!', 'danger')
            
        # የደንበኛ በቆጣሪ ቁጥር መግቢያ
        elif meter_num:
            user = User.query.filter_by(meter_number=meter_num, role='customer').first()
            if user:
                session.clear()
                session['user_id'] = user.id
                session['role'] = 'customer'
                return redirect(url_for('customer_dashboard'))
            flash('ይህ የቆጣሪ ቁጥር አልተገኘም!', 'danger')
            
    return render_template('login.html')

# 📊 1. የአስተዳዳሪ ማዕከል
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    config = SystemConfig.query.first()
    customers = User.query.filter_by(role='customer').all()
    
    total_collected = db.session.query(db.func.sum(Bill.total_amount)).filter(Bill.month_name == config.current_month_name, Bill.status == 'Paid').scalar() or 0.0
    total_unpaid = sum(c.balance for c in customers if c.status == 'Unpaid')
    
    high_consumers = []
    for c in customers:
        consumption = max(0.0, c.current_reading - c.previous_reading)
        if consumption >= 20:
            high_consumers.append({'name': c.name, 'meter': c.meter_number, 'usage': consumption})
            
    return render_template('admin.html', customers=customers, total_collected=total_collected, total_unpaid=total_unpaid,
                           current_month=config.current_month_name, due_date=config.due_date, config=config, high_consumers=high_consumers)

@app.route('/admin/update_config', methods=['POST'])
def update_config():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    config = SystemConfig.query.first()
    if config:
        config.due_date = request.form['due_date']
        config.office_phone = request.form['office_phone']
        config.office_address = request.form['office_address']
        config.bank_account = request.form['bank_account']
        db.session.commit()
        flash('የቢሮ መረጃዎች ታድሰዋል!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_customer', methods=['POST'])
def add_customer():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    new_cust = User(
        name=request.form['name'], username=request.form['username'], password='123',
        phone=request.form['phone'], meter_number=request.form['meter_number'], role='customer'
    )
    try:
        db.session.add(new_cust)
        db.session.commit()
        flash('አዲስ ደንበኛ ተመዝግቧል!', 'success')
    except:
        flash('ስህተት ተከስቷል! የቆጣሪ ወይም የተጠቃሚ ስም ተደግሟል።', 'danger')
    return redirect(url_for('admin_dashboard'))

# 📱 2. የቆጣሪ አንባቢ ማዕከል
@app.route('/reader', methods=['GET', 'POST'])
def reader_dashboard():
    if session.get('role') != 'reader': return redirect(url_for('login'))
    config = SystemConfig.query.first()
    customers = User.query.filter_by(role='customer').all()
    
    if request.method == 'POST':
        user_id = request.form['user_id']
        current_read = float(request.form['current_reading'])
        user = User.query.get(user_id)
        
        if user and current_read >= user.previous_reading:
            consumption = current_read - user.previous_reading
            user.base_bill = calculate_block_tariff(consumption)
            
            today_str = datetime.now().strftime('%Y-%m-%d')
            user.penalty = 100.0 if today_str > config.due_date else 0.0
            
            user.current_reading = current_read
            user.balance = user.base_bill + user.old_debt + user.penalty
            user.status = 'Unpaid' if user.balance > 0 else 'Paid'
            
            db.session.commit()
            flash(f'ለ {user.name} የዚህ ወር ንባብ ገብቷል! ፍጆታ፡ {consumption} ዩኒት።', 'success')
        else:
            flash('ስህተት፡ የአሁኑ ንባብ ካለፈው ወር ሊያንስ አይችልም!', 'danger')
            
    return render_template('reader.html', customers=customers, current_month=config.current_month_name)

# 💳 3. የሂሳብ ክፍያ መቀበያ
@app.route('/admin/pay_bill/<int:id>')
def pay_bill(id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    user = User.query.get(id)
    config = SystemConfig.query.first()
    if user:
        consumption = max(0.0, user.current_reading - user.previous_reading)
        new_bill = Bill(
            user_id=user.id, customer_name=user.name, meter_number=user.meter_number,
            month_name=config.current_month_name, prev_reading=user.previous_reading,
            curr_reading=user.current_reading, consumption=consumption,
            base_amount=user.base_bill, penalty_amount=user.penalty, old_debt_amount=user.old_debt,
            total_amount=user.balance, status='Paid'
        )
        db.session.add(new_bill)
        
        user.previous_reading = user.current_reading if user.current_reading > 0 else user.previous_reading
        user.current_reading, user.base_bill, user.penalty, user.old_debt, user.balance = 0.0, 0.0, 0.0, 0.0, 0.0
        user.status = 'Paid'
        db.session.commit()
        flash('ክፍያ ተፈጽሞ መረጃው ወደ ታሪክ መዝገብ ተዛውሯል!', 'success')
    return redirect(url_for('admin_dashboard'))

# 🔄 4. የወር ማሻገሪያ
@app.route('/admin/next_month', methods=['POST'])
def next_month():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    next_month_name = request.form['next_month_name']
    config = SystemConfig.query.first()
    old_month = config.current_month_name
    
    customers = User.query.filter_by(role='customer').all()
    for c in customers:
        consumption = max(0.0, c.current_reading - c.previous_reading)
        if c.status == 'Unpaid':
            history_bill = Bill(
                user_id=c.id, customer_name=c.name, meter_number=c.meter_number,
                month_name=old_month, prev_reading=c.previous_reading,
                curr_reading=c.current_reading, consumption=consumption,
                base_amount=c.base_bill, penalty_amount=c.penalty, old_debt_amount=c.old_debt,
                total_amount=c.balance, status='Unpaid'
            )
            db.session.add(history_bill)
            c.old_debt = c.balance 
        else:
            c.old_debt = 0.0
