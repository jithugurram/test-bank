from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import LoginManager, login_required, current_user, login_user, logout_user, UserMixin
from flask_login import UserMixin

# --------------------
# Flask App Config
# --------------------
app = Flask(__name__)
app.secret_key = "secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bank.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------------
# Flask-Login Setup
# --------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # Redirects to login page if not logged in


# --------------------
# Database Models
# --------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    pin = db.Column(db.String(4), nullable=False)
    balance = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f"<User {self.username}>"


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'Deposit' or 'Withdraw'
    amount = db.Column(db.Float, nullable=False)
    balance = db.Column(db.Float, nullable=False)  # Balance after this transaction
    date = db.Column(db.DateTime, default=datetime.utcnow)

# --------------------
# Flask-Login User Loader
# --------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --------------------
# Routes
# --------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

# --------------------
# Signup
# --------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        pin = request.form['pin']

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already exists! Please log in instead.", "error")
            return redirect(url_for('signup'))

        # Create new user
        new_user = User(username=username, email=email, password=password, pin=pin, balance=0.0)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error during signup: {str(e)}", "error")
            return redirect(url_for('signup'))

    return render_template('signup.html')


# --------------------
# Login
# --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        pin = request.form['pin']

        print(f"Login Attempt: username={username}, password={password}, pin={pin}")

        # Validate username, password, and pin
        user = User.query.filter_by(username=username, password=password, pin=pin).first()

        if user:
            login_user(user)  # Flask-Login handles session
            print(f"Login successful for: {username}")
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            print("Login failed! Invalid credentials.")
            flash("Invalid username, password, or PIN.", "danger")

    return render_template('login.html')


@app.route("/forgot_password")
def forgot_password():
    return "Forgot Password Page - Coming Soon!"


# --------------------
# Logout
# --------------------
@app.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))


# --------------------
# Dashboard
# --------------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


# --------------------
# Deposit
# --------------------
@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            pin = request.form['pin']
            note = request.form.get('note', '')

            if amount <= 0:
                flash("Deposit amount must be greater than 0.", "error")
                return redirect(url_for('deposit'))

            if pin != current_user.pin:
                flash("Invalid transaction PIN.", "error")
                return redirect(url_for('deposit'))

            # Update balance
            current_user.balance += amount

            # Save transaction
            new_txn = Transaction(
                user_id=current_user.id,
                type="Deposit",
                amount=amount,
                balance=current_user.balance
            )
            db.session.add(new_txn)
            db.session.commit()

            flash(f"Successfully deposited ₹{amount:.2f}! New balance: ₹{current_user.balance:.2f}", "success")
            return redirect(url_for('dashboard'))

        except ValueError:
            flash("Please enter a valid amount.", "error")
            return redirect(url_for('deposit'))

    return render_template('deposit.html', user=current_user)



# --------------------
# Withdraw
# --------------------
@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
            pin = request.form['pin']

            if amount <= 0:
                flash("Withdrawal amount must be greater than 0.", "error")
                return redirect(url_for('withdraw'))

            if pin != current_user.pin:
                flash("Invalid transaction PIN.", "error")
                return redirect(url_for('withdraw'))

            if amount > current_user.balance:
                flash("Insufficient balance for this withdrawal.", "error")
                return redirect(url_for('withdraw'))

            # Deduct balance
            current_user.balance -= amount

            # Save transaction
            new_txn = Transaction(
                user_id=current_user.id,
                type="Withdraw",
                amount=amount,
                balance=current_user.balance
            )
            db.session.add(new_txn)
            db.session.commit()

            flash(f"Successfully withdrew ₹{amount:.2f}! New balance: ₹{current_user.balance:.2f}", "success")
            return redirect(url_for('dashboard'))

        except ValueError:
            flash("Please enter a valid amount.", "error")
            return redirect(url_for('withdraw'))

    return render_template('withdraw.html', user=current_user)


# --------------------
# Transfer
# --------------------
@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if request.method == 'POST':
        to_username = request.form.get('to_username').strip()
        amount = float(request.form.get('amount'))
        note = request.form.get('note')
        pin = request.form.get('pin')

        # Step 1: Validate PIN
        if not check_password_hash(current_user.password, pin):
            flash("❌ Incorrect transaction PIN!", "danger")
            return redirect(url_for('transfer'))

        # Step 2: Check recipient exists
        recipient = User.query.filter_by(username=to_username).first()
        if not recipient:
            flash("❌ Recipient not found!", "danger")
            return redirect(url_for('transfer'))

        # Step 3: Prevent sending money to yourself
        if recipient.id == current_user.id:
            flash("⚠️ You cannot transfer money to yourself!", "warning")
            return redirect(url_for('transfer'))

        # Step 4: Check balance
        if current_user.balance < amount or amount <= 0:
            flash("❌ Insufficient balance or invalid amount!", "danger")
            return redirect(url_for('transfer'))

        # Step 5: Perform transfer
        current_user.balance -= amount
        recipient.balance += amount

        # Record both transactions
        sender_txn = Transaction(
            user_id=current_user.id,
            type="Transfer Sent",
            amount=-amount,
            balance=current_user.balance
        )
        recipient_txn = Transaction(
            user_id=recipient.id,
            type="Transfer Received",
            amount=amount,
            balance=recipient.balance
        )

        db.session.add(sender_txn)
        db.session.add(recipient_txn)
        db.session.commit()

        flash(f"✅ Transfer successful! ₹{amount:.2f} sent to {recipient.username}", "success")
        return redirect(url_for('dashboard'))

    return render_template('transfer.html', user=current_user)


# --------------------
# Check recipient dynamically (AJAX endpoint)
# --------------------
@app.route('/get_recipient/<username>', methods=['GET'])
@login_required
def get_recipient(username):
    recipient = User.query.filter_by(username=username).first()
    if recipient:
        return jsonify({"exists": True, "name": recipient.username})
    else:
        return jsonify({"exists": False})


# --------------------
# Transaction History
# --------------------
@app.route("/transactions")
@login_required
def transactions():
    txns = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    return render_template("transactions.html", user=current_user, transactions=txns)


# --------------------
# Initialize DB
# --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=3000, debug=True)
