import os
import csv
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'beto_water_super_secret_key_2026_perfect_final_v10'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///beto_water_v10.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy()
db.init_app(app)

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tariff_rate = db.Column(db.Float, default=15.0)
    current_month_name = db.Column(db.String(50), default="ጥቅምት")

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
    status = db.Column(db.String(20), default='Paid')

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    month_name = db.Column(db.String(50), nullable=False)
    prev_reading = db.Column(db.Float, nullable=False)
    curr_reading = db.Column(db.Float, nullable=False)
    consumption = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Unpaid')

with app.app_context():
    db.create_all()
    if not SystemConfig.query.first():
        config = SystemConfig(tariff_rate=15.0, current_month_name="ጥቅምት")
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
    customers = User.query.filter_by(role='customer').all()
    total_pending = sum(c.balance for c in customers if c.status == 'Unpaid')
    config = SystemConfig.query.first()
    current_tariff = config.tariff_rate if config else 15.0
    current_month = config.current_month_name if config else "ጥቅምት"
    
    graph_labels = []
    graph_data = []
    for c in customers:
        consumption = max(0.0, c.current_reading - c.previous_reading)
        graph_labels.append(c.name)
        graph_data.append(consumption)
        
    return render_template('admin.html', customers=customers, total_pending=total_pending, 
                           current_tariff=current_tariff, current_month=current_month,
                           graph_labels=graph_labels, graph_data=graph_data)

@app.route('/admin/update_tariff', methods=['POST'])
def update_tariff():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    new_rate = float(request.form['tariff_rate'])
    config = SystemConfig.query.first()
    if config:
        config.tariff_rate = new_rate
        db.session.commit()
        flash(f'ታሪፍ በስኬት ተቀይሯል!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/next_month', methods=['POST'])
def next_month():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    next_month_name = request.form['next_month_name']
    config = SystemConfig.query.first()
    old_month = config.current_month_name
    customers = User.query.filter_by(role='customer').all()
    for c in customers:
        if c.current_reading > 0:
            consumption = c.current_reading - c.previous_reading
            tariff = config.tariff_rate if config else 15.0
            amount = consumption * tariff
            history_bill = Bill(
                user_id=c.id, month_name=old_month, prev_reading=c.previous_reading,
                curr_reading=c.current_reading, consumption=consumption, amount=amount, status=c.status
            )
            db.session.add(history_bill)
            c.previous_reading = c.current_reading 
        c.current_reading = 0.0 
    if config:
        config.current_month_name = next_month_name
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/send_sms/<int:id>')
def send_sms(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user = User.query.get(id)
    config = SystemConfig.query.first()
    month = config.current_month_name if config else "ወርሃዊ"
    if user and user.status == 'Unpaid':
        sms_message = f"ክቡር ደንበኛ {user.name}፣ የ{month} ወር የውሃ ክፍያዎ {user.balance} ብር ስለሆነ እባክዎ በቴሌብር ይክፈሉ።"
        print(f"SMS ተልኳል ወደ {user.phone}፦ {sms_message}") 
        flash(f"የክፍያ ማሳሰቢያ SMS ወደ {user.phone} በስኬት ተልኳል!", "success")
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
    new_cust = User(name=name, username=username, password=password, phone=phone, meter_number=meter_number)
    try:
        db.session.add(new_cust)
        db.session.commit()
    except:
        pass
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_customer/<int:id>')
def delete_customer(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user = User.query.get(id)
    if user:
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/enter_reading', methods=['POST'])
def enter_reading():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user_id = request.form['user_id']
    current_read = float(request.form['current_reading'])
    user = User.query.get(user_id)
    config = SystemConfig.query.first()
    tariff = config.tariff_rate if config else 15.0
    if user and current_read >= user.previous_reading:
        consumption = current_read - user.previous_reading
        bill_amount = consumption * tariff
        user.current_reading = current_read
        user.balance += bill_amount
        if user.balance > 0:
            user.status = 'Unpaid'
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/pay_bill/<int:id>')
def pay_bill(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    user = User.query.get(id)
    if user:
        user.balance = 0.0
        user.status = 'Paid'
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export_excel')
def export_excel():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    config = SystemConfig.query.first()
    active_month = config.current_month_name if config else ""
    customers = User.query.filter_by(role='customer').all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['በቶ ከተማ አስተዳደር ውሃና ፍሳሽ ጽ/ቤት የደንበኞች መረጃ መዝገብ'])
    cw.writerow([f'የሪፖርት ወር: {active_month}'])
    cw.writerow([]) 
    cw.writerow(['የደንበኛ ሙሉ ስም', 'ስልክ ቁጥር', 'የቆጣሪ ቁጥር', 'የቀድሞ ንባብ', 'የአሁኑ ንባብ', 'የወሩ ፍጆታ (ዩኒት)', 'የሚከፈልበት ሂሳብ (ብር)', 'የክፍያ ሁኔታ'])
    for c in customers:
        status_text = 'ተከፍሏል' if c.status == 'Paid' else 'አልተከፈለም'
        consumption = max(0.0, c.current_reading - c.previous_reading)
        cw.writerow([c.name, c.phone, c.meter_number, c.previous_reading, c.current_reading, consumption, c.balance, status_text])
    output = make_response(si.getvalue().encode('utf-8-sig'))
    output.headers["Content-Disposition"] = f"attachment; filename=Beto_Water_Report_{active_month}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/customer')
def customer_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    config = SystemConfig.query.first()
    current_month = config.current_month_name if config else "ጥቅምት"
    history_bills = Bill.query.filter_by(user_id=user.id).all()
    return render_template('customer.html', user=user, current_month=current_month, history_bills=history_bills)

@app.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for('login')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
