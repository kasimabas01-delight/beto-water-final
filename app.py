import os
import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'beto_water_super_secret_key_2026_perfect_final_v20'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///beto_water_v20.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
db.init_app(app)

# 🚀 ሲስተም ቅንብር (ታሪፍ፣ ወር እና የመጨረሻ መክፈያ ቀን)
class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tariff_rate = db.Column(db.Float, default=15.0)
    current_month_name = db.Column(db.String(50), default="ጥቅምት")
    due_date = db.Column(db.String(50), default="2026-10-30")  # የመጨረሻ መክፈያ ቀን

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='customer')
    phone = db.Column(db.String(20))
    meter_number = db.Column(db.String(50), unique=True, nullable=True)
    previous_reading = db.Column(db.Float, default=0.0)
    current_reading = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)
    penalty = db.Column(db.Float, default=0.0)  # የቅጣት መጠን
    status = db.Column(db.String(20), default='Paid')

# 🚀 የታሪክ መዝገብ ሰንጠረዥ (የወራትን መረጃ ለብቻ ለብቻ ለመያዝ)
class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(100))
    meter_number = db.Column(db.String(50))
    month_name = db.Column(db.String(50), nullable=False)
    prev_reading = db.Column(db.Float, nullable=False)
    curr_reading = db.Column(db.Float, nullable=False)
    consumption = db.Column(db.Float, nullable=False)
    base_amount = db.Column(db.Float, nullable=False)  # ዋና ክፍያ
    penalty_amount = db.Column(db.Float, default=0.0) # ቅጣት
    total_amount = db.Column(db.Float, nullable=False) # ጠቅላላ ዕዳ
    status = db.Column(db.String(20), default='Unpaid')

with app.app_context():
    db.create_all()
    if not SystemConfig.query.first():
        config = SystemConfig(tariff_rate=15.0, current_month_name="ጥቅምት", due_date="2026-10-30")
        db.session.add(config)
    db.session.commit()

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if 'username' in request.form and 'password' in request.form:
            username = request.form['username'].strip()
            password = request.form['password'].strip()
            
            if username == 'beto' and password == 'beto@1234':
                session.clear()
                session['role'] = 'admin'
                session['user_id'] = 9999
                session['name'] = 'ዋና አስተዳዳሪ'
                return redirect(url_for('admin_dashboard'))
            flash('የአስተዳዳሪ ስም ወይም የይለፍ ቃል ተሳስቷል!', 'danger')
            
        elif 'meter_number' in request.form:
            meter_num = request.form['meter_number'].strip()
            user = User.query.filter_by(meter_number=meter_num, role='customer').first()
            if user:
                session.clear()
                session['user_id'] = user.id
                session['role'] = user.role
                session['name'] = user.name
                return redirect(url_for('customer_dashboard'))
            else:
                flash('ይህ የቆጣሪ ቁጥር በሲስተሙ ውስጥ አልተገኘም!', 'danger')
                
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    config = SystemConfig.query.first()
    current_tariff = config.tariff_rate if config else 15.0
    current_month = config.current_month_name if config else "ጥቅምት"
    due_date_str = config.due_date if config else "2026-10-30"
    
    customers = User.query.filter_by(role='customer').all()
    
    # 🚀 በየወሩ የተሰበሰበ እና ቀሪ ዕዳ በራስ-ሰር ማስላት
    total_collected = db.session.query(db.func.sum(Bill.total_amount)).filter(Bill.month_name == current_month, Bill.status == 'Paid').scalar() or 0.0
    total_unpaid = sum(c.balance for c in customers if c.status == 'Unpaid')
    
    graph_labels = []
    graph_data = []
    for c in customers:
        consumption = max(0.0, c.current_reading - c.previous_reading)
        graph_labels.append(c.name)
        graph_data.append(consumption)
        
    return render_template('admin.html', customers=customers, total_collected=total_collected, total_unpaid=total_unpaid,
                           current_tariff=current_tariff, current_month=current_month, due_date=due_date_str,
                           graph_labels=graph_labels, graph_data=graph_data)

@app.route('/admin/update_config', methods=['POST'])
def update_config():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    config = SystemConfig.query.first()
    if config:
        config.tariff_rate = float(request.form['tariff_rate'])
        config.due_date = request.form['due_date']
        db.session.commit()
        flash('የቢሮ ቅንብሮች በስኬት ታድሰዋል!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_customer', methods=['POST'])
def add_customer():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    name = request.form['name']
    username = request.form['username']
    password = request.form['password']
    phone = request.form['phone']
    meter_number = request.form['meter_number']
    new_cust = User(name=name, username=username, password=password, phone=phone, meter_number=meter_number, balance=0.0, penalty=0.0, status='Paid')
    try:
        db.session.add(new_cust)
        db.session.commit()
        flash('አዲስ ደንበኛ በስኬት ተመዝግቧል!', 'success')
    except:
        flash('ስህተት ተከስቷል! የቆጣሪ ቁጥር ወይም የተጠቃሚ ስም ተደግሟል።', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/enter_reading', methods=['POST'])
def enter_reading():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user_id = request.form['user_id']
    current_read = float(request.form['current_reading'])
    user = User.query.get(user_id)
    config = SystemConfig.query.first()
    
    if user and current_read >= user.previous_reading:
        consumption = current_read - user.previous_reading
        base_bill = consumption * config.tariff_rate
        
        # 🚀 ከመክፈያ ቀን ያሳለፉ ሰዎችን በራስ-ሰር አይቶ 100 ብር ቅጣት መጨመሪያ ስሌት
        today_str = datetime.now().strftime('%Y-%m-%d')
        penalty_amount = 0.0
        if today_str > config.due_date:
            penalty_amount = 100.0
            
        user.current_reading = current_read
        user.penalty = penalty_amount
        user.balance = base_bill + penalty_amount
        
        if user.balance > 0:
            user.status = 'Unpaid'
            
        db.session.commit()
        flash('የወሩ ንባብ እና የቅጣት ስሌት በትክክል ተሰልቷል!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/pay_bill/<int:id>')
def pay_bill(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user = User.query.get(id)
    config = SystemConfig.query.first()
    if user:
        # የወሩን ክፍያ ወደ ታሪክ ማህደር ማስገባት
        consumption = user.current_reading - user.previous_reading
        base_bill = consumption * config.tariff_rate
        
        new_bill_history = Bill(
            user_id=user.id, customer_name=user.name, meter_number=user.meter_number,
            month_name=config.current_month_name, prev_reading=user.previous_reading,
            curr_reading=user.current_reading, consumption=consumption,
            base_amount=base_bill, penalty_amount=user.penalty, total_amount=user.balance, status='Paid'
        )
        db.session.add(new_bill_history)
        
        # የደንበኛውን የዚህ ወር ሂሳብ ማጽዳት
        user.previous_reading = user.current_reading
        user.current_reading = 0.0
        user.balance = 0.0
        user.penalty = 0.0
        user.status = 'Paid'
        db.session.commit()
        flash('ክፍያ ተፈጽሞ መረጃው ወደ ወርሃዊ የታሪክ ማህደር ተዛውሯል!', 'success')
    return redirect(url_for('admin_dashboard'))

# 🚀 አዲስ - ወር ሲቀየር ያልከፈሉትን ዕዳ ይዞ ወደ ታሪክ ማዛወሪያ
@app.route('/admin/next_month', methods=['POST'])
def next_month():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    next_month_name = request.form['next_month_name']
    config = SystemConfig.query.first()
    old_month = config.current_month_name
    
    customers = User.query.filter_by(role='customer').all()
    for c in customers:
        if c.status == 'Unpaid':
            consumption = c.current_reading - c.previous_reading
            base_bill = consumption * config.tariff_rate
            
            history_bill = Bill(
                user_id=c.id, customer_name=c.name, meter_number=c.meter_number,
                month_name=old_month, prev_reading=c.previous_reading,
                curr_reading=c.current_reading, consumption=consumption,
                base_amount=base_bill, penalty_amount=c.penalty, total_amount=c.balance, status='Unpaid'
            )
            db.session.add(history_bill)
            c.previous_reading = c.current_reading
            c.current_reading = 0.0
            c.balance = 0.0
            c.penalty = 0.0
            c.status = 'Paid'
            
    config.current_month_name = next_month_name
    db.session.commit()
    flash(f'የሲስተሙ ወር ወደ {next_month_name} ተሸጋግሯል!', 'success')
    return redirect(url_for('admin_dashboard'))

# 🚀 የወራትን መረጃ ለብቻ ለብቻ በExcel ማውረጃ የላቀ አሰራር
@app.route('/admin/export_excel/<string:month_name>')
def export_excel(month_name):
    if session.get('role') != 'admin':
