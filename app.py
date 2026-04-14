from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
import os
import logging

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change_this_in_production')

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///karthik_rrn.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get(
    'MAIL_DEFAULT_SENDER',
    app.config['MAIL_USERNAME']
)

# Fast2SMS API Key
FAST2SMS_API_KEY = os.environ.get('FAST2SMS_API_KEY', '')

# Initialize extensions (ONLY ONCE)
db = SQLAlchemy(app)
mail = Mail(app)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── DATABASE MODELS ─────────────────────────────────────────

class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    mobile   = db.Column(db.String(10), unique=True, nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=True)
    name     = db.Column(db.String(100), default='')
    created  = db.Column(db.DateTime, default=datetime.utcnow)
    searches = db.relationship('Transaction', backref='user', lazy=True)

class OTP(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    mobile  = db.Column(db.String(10), nullable=True)
    email   = db.Column(db.String(120), nullable=True)
    otp     = db.Column(db.String(6), nullable=False)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    used    = db.Column(db.Boolean, default=False)

class Transaction(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    rrn         = db.Column(db.String(12), nullable=False)
    app_name    = db.Column(db.String(50))
    status      = db.Column(db.String(20))
    amount      = db.Column(db.Float)
    merchant    = db.Column(db.String(100))
    bank        = db.Column(db.String(100))
    timestamp   = db.Column(db.String(60))
    searched_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'))

# ─── PAYMENT APPS ────────────────────────────────────────────

PAYMENT_APPS = [
    {"id": "phonepe",    "name": "PhonePe",    "icon": "📱"},
    {"id": "paytm",      "name": "Paytm",       "icon": "💙"},
    {"id": "gpay",       "name": "Google Pay",  "icon": "🔵"},
    {"id": "amazonpay",  "name": "Amazon Pay",  "icon": "🟠"},
    {"id": "bookmyshow", "name": "BookMyShow",  "icon": "🎬"},
    {"id": "meesho",     "name": "Meesho",      "icon": "🛍️"},
    {"id": "swiggy",     "name": "Swiggy",      "icon": "🍔"},
    {"id": "zomato",     "name": "Zomato",      "icon": "🍕"},
    {"id": "cred",       "name": "CRED",         "icon": "💳"},
]

MERCHANTS = {
    "phonepe":    ["Reliance Jio", "Flipkart", "BigBazaar", "IRCTC", "Myntra"],
    "paytm":      ["Paytm Mall", "Movies", "Travel", "Games", "Utilities"],
    "gpay":       ["Google Store", "YouTube Premium", "Play Store", "Tata Sky"],
    "amazonpay":  ["Amazon.in", "Prime Video", "Amazon Fresh", "Pantry"],
    "bookmyshow": ["PVR Cinemas", "INOX", "Carnival Cinemas", "SPI Cinemas"],
    "meesho":     ["Meesho Store", "Fashion Hub", "Electronics Zone"],
    "swiggy":     ["KFC", "McDonald's", "Domino's", "Burger King", "Pizza Hut"],
    "zomato":     ["Zomato Kitchen", "Blinkit", "Gold Restaurant"],
    "cred":       ["CRED Store", "CRED Travel", "CRED Pay"],
}

BANKS = [
    "HDFC Bank", "State Bank of India", "ICICI Bank", "Axis Bank",
    "Kotak Mahindra Bank", "Yes Bank", "Punjab National Bank",
    "Bank of Baroda", "Canara Bank", "Union Bank of India"
]

# ─── OTP ─────────────────────────────────────────────────────

def send_otp_sms(mobile, otp):
    """Send OTP via Fast2SMS. Returns (success_bool, message_str)"""
    try:
        if not FAST2SMS_API_KEY:
            logger.warning("Fast2SMS API key not configured")
            return False, "SMS service not configured"

        response = requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            headers={"authorization": FAST2SMS_API_KEY},
            data={
                "route": "otp",
                "variables_values": otp,
                "flash": 0,
                "numbers": mobile,
            },
            timeout=10
        )
        result = response.json()
        if result.get("return"):
            logger.info(f"SMS sent to {mobile} via Fast2SMS")
            return True, "OTP sent via SMS"
        else:
            logger.error(f"Fast2SMS error: {result}")
            return False, result.get("message", ["SMS sending failed"])[0]
    except Exception as e:
        logger.error(f"Fast2SMS SMS error: {e}")
        return False, str(e)

def send_otp_email(email, otp, name="User"):
    """Send OTP via Email. Returns (success_bool, message_str)"""
    try:
        msg = Message(
            subject='RRN Checker - Your OTP',
            recipients=[email],
            html=f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #1a56db;">RRN Checker - OTP Verification</h2>
                <p>Hi {name},</p>
                <p>Your one-time password (OTP) is:</p>
                <div style="background: #f3f4f6; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
                    <h1 style="color: #1a56db; letter-spacing: 5px; margin: 0;">{otp}</h1>
                </div>
                <p><strong>This OTP is valid for 5 minutes only.</strong></p>
                <p style="color: #dc2626; font-weight: bold;">⚠️ Do not share this OTP with anyone.</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                <p style="color: #6b7280; font-size: 12px;">
                    If you didn't request this OTP, please ignore this email.
                    <br>Built by Karthik • SR University
                </p>
            </div>
            """
        )
        mail.send(msg)
        logger.info(f"Email sent to {email}")
        return True, "OTP sent via Email"
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False, str(e)

# ─── RRN LOGIC ───────────────────────────────────────────────

def get_transaction(rrn, app_id):
    """
    RRN is exactly 12 digits.
    Status logic (deterministic so same RRN always gives same result):
      - First 2 digits in [10,11,20,22,30,33,99] → failed
      - Sum of all 12 digits is even              → success
      - Sum of all 12 digits is odd               → pending
    """
    random.seed(rrn + app_id)

    digit_sum = sum(int(d) for d in rrn)
    prefix    = rrn[:2]

    if prefix in ["10","11","20","22","30","33","99"]:
        status = "failed"
    elif digit_sum % 2 == 0:
        status = "success"
    else:
        status = "pending"

    merchant  = random.choice(MERCHANTS.get(app_id, ["Unknown Merchant"]))
    bank      = random.choice(BANKS)
    amount    = round(random.uniform(49, 9999), 2)
    days_ago  = random.randint(0, 30)
    txn_dt    = datetime.now() - timedelta(
        days=days_ago,
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )

    # Refund timeline only for failed transactions
    timeline = None
    if status == "failed":
        timeline = [
            {
                "step": "Transaction Failed",
                "date": txn_dt.strftime("%d %b %Y, %I:%M %p"),
                "done": True
            },
            {
                "step": "Refund Initiated",
                "date": (txn_dt + timedelta(hours=2)).strftime("%d %b %Y, %I:%M %p"),
                "done": True
            },
            {
                "step": "Bank Processing",
                "date": (txn_dt + timedelta(days=2)).strftime("%d %b %Y"),
                "done": days_ago >= 2
            },
            {
                "step": "Refund Credited to Account",
                "date": (txn_dt + timedelta(days=7)).strftime("%d %b %Y"),
                "done": days_ago >= 7
            },
        ]

    return {
        "rrn":      rrn,
        "app_name": next((a["name"] for a in PAYMENT_APPS if a["id"] == app_id), app_id),
        "status":   status,
        "amount":   amount,
        "merchant": merchant,
        "bank":     bank,
        "utr":      ''.join(random.choices(string.digits, k=12)),
        "txn_id":   ''.join(random.choices(string.ascii_uppercase + string.digits, k=16)),
        "timestamp":txn_dt.strftime("%d %b %Y, %I:%M %p"),
        "mode":     random.choice(["UPI", "Debit Card", "Credit Card", "Net Banking"]),
        "vpa":      f"user{random.randint(1000,9999)}@{app_id}",
        "timeline": timeline,
    }

# ─── ROUTES ──────────────────────────────────────────────────

@app.route("/")
def index():
    if "mobile" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", apps=PAYMENT_APPS)

@app.route("/login")
def login():
    if "mobile" in session:
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    data = request.get_json()
    mobile = data.get("mobile", "").strip()
    email = data.get("email", "").strip()
    method = data.get("method", "sms")  # "sms" or "email"

    # Validate input
    if method == "sms":
        if not mobile.isdigit() or len(mobile) != 10:
            return jsonify({"ok": False, "msg": "Enter a valid 10-digit mobile number."})
    elif method == "email":
        if not email or "@" not in email:
            return jsonify({"ok": False, "msg": "Enter a valid email address."})
    else:
        return jsonify({"ok": False, "msg": "Invalid method."})

    # Generate OTP
    otp = ''.join(random.choices(string.digits, k=6))
    
    # Save OTP to database
    otp_record = OTP(
        mobile=mobile if method == "sms" else None,
        email=email if method == "email" else None,
        otp=otp
    )
    db.session.add(otp_record)
    db.session.commit()

    # Send OTP
    if method == "sms":
        sent, msg = send_otp_sms(mobile, otp)
        if sent:
            return jsonify({"ok": True, "msg": f"OTP sent to +91 {mobile[:4]}XXXXXX"})
        else:
            # Fallback: show demo OTP if SMS fails
            logger.warning(f"SMS failed for {mobile}, showing demo OTP")
            return jsonify({"ok": True, "msg": "SMS unavailable - using demo OTP", "demo": otp})
    else:  # email
        user_name = data.get("name", "User")
        sent, msg = send_otp_email(email, otp, user_name)
        if sent:
            return jsonify({"ok": True, "msg": f"OTP sent to {email[:3]}***@{email.split('@')[1]}"})
        else:
            return jsonify({"ok": False, "msg": f"Failed to send email: {msg}"})

@app.route("/verify_otp", methods=["POST"])
def verify_otp_route():
    data = request.get_json()
    mobile = data.get("mobile", "").strip()
    email = data.get("email", "").strip()
    otp = data.get("otp", "").strip()

    # Find OTP record
    if mobile:
        rec = OTP.query.filter_by(mobile=mobile, used=False)\
                       .order_by(OTP.id.desc()).first()
    elif email:
        rec = OTP.query.filter_by(email=email, used=False)\
                       .order_by(OTP.id.desc()).first()
    else:
        return jsonify({"ok": False, "msg": "No mobile or email provided."})

    if not rec:
        return jsonify({"ok": False, "msg": "OTP not found. Request a new one."})
    
    if datetime.utcnow() - rec.created > timedelta(minutes=5):
        return jsonify({"ok": False, "msg": "OTP expired. Request a new one."})
    
    if rec.otp != otp:
        return jsonify({"ok": False, "msg": "Wrong OTP. Try again."})

    # Mark OTP as used
    rec.used = True

    # Create or update user
    if mobile:
        user = User.query.filter_by(mobile=mobile).first()
        if not user:
            user = User(mobile=mobile, name=f"User{mobile[-4:]}")
            db.session.add(user)
        db.session.commit()
        session["mobile"] = mobile
    elif email:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, name=email.split('@')[0])
            db.session.add(user)
        db.session.commit()
        session["email"] = email

    session["user_id"] = user.id
    return jsonify({"ok": True})

@app.route("/check_rrn", methods=["POST"])
def check_rrn():
    if "mobile" not in session and "email" not in session:
        return jsonify({"ok": False, "msg": "Not logged in."}), 401
    
    data = request.get_json()
    rrn = data.get("rrn", "").strip()
    app_id = data.get("app_id", "").strip()

    if not (rrn.isdigit() and len(rrn) == 12):
        return jsonify({"ok": False, "msg": "RRN must be exactly 12 digits."})
    if not app_id:
        return jsonify({"ok": False, "msg": "Select a payment app first."})

    result = get_transaction(rrn, app_id)

    db.session.add(Transaction(
        rrn=rrn,
        app_name=result["app_name"],
        status=result["status"],
        amount=result["amount"],
        merchant=result["merchant"],
        bank=result["bank"],
        timestamp=result["timestamp"],
        user_id=session.get("user_id")
    ))
    db.session.commit()

    return jsonify({"ok": True, "data": result})

@app.route("/history")
def history():
    if "mobile" not in session and "email" not in session:
        return redirect(url_for("login"))
    
    user = User.query.filter_by(id=session.get("user_id")).first()
    if not user:
        return redirect(url_for("login"))
    
    txns = Transaction.query.filter_by(user_id=user.id)\
                            .order_by(Transaction.searched_at.desc()).limit(20).all()
    
    display_id = session.get("mobile") or session.get("email")
    return render_template("history.html", txns=txns, mobile=display_id)

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json()
    message = data.get("message", "").strip()
    history = data.get("history", [])
    
    if not message:
        return jsonify({"reply": "Please type something."})

    SYSTEM = """You are a helpful customer support assistant for an RRN transaction status checker website built by Karthik (SR University student).
You help Indian users with UPI/payment questions. Keep replies short, clear, and friendly.

Key facts:
- RRN (Reference Retrieval Number) is a unique 12-digit number given to every UPI/bank transaction by the acquiring bank
- It is used to trace and verify transactions between banks via the NPCI network
- Money gets stuck due to: network timeout during payment, bank server failure, double debit, UPI gateway glitch
- Refund timelines: UPI 3-5 business days | Debit card 5-7 days | Credit card 7-10 days
- Failed UPI transactions auto-reverse within 24-48 hours per RBI guidelines
- If not reversed after 5 days, file dispute at your bank with the RRN number
- NPCI dispute portal: https://www.npci.org.in/
- Users can also complain on RBI Sachet portal: https://sachet.rbi.org.in/
- Where to find RRN: PhonePe → transaction details → Reference ID | Paytm → order history → UTR | GPay → payment receipt
- Reply in the same language the user uses (Telugu, Hindi, or English)
- Never give specific legal/financial advice
- Keep replies under 80 words unless explanation is complex"""

    try:
        msgs = history[-6:] + [{"role": "user", "content": message}]
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": SYSTEM,
                "messages": msgs,
            },
            timeout=15
        )
        reply = r.json()["content"][0]["text"]
        return jsonify({"reply": reply})
    except Exception as e:
        logger.error(f"Chatbot error: {e}")
        return jsonify({"reply": "I'm having trouble right now. Please try again in a moment."})

# ─── ADMIN ───────────────────────────────────────────────────

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
        else:
            return render_template("admin_login.html", error="Wrong password.")
    
    if not session.get("is_admin"):
        return render_template("admin_login.html", error=None)

    stats = {
        "users": User.query.count(),
        "total": Transaction.query.count(),
        "success": Transaction.query.filter_by(status="success").count(),
        "pending": Transaction.query.filter_by(status="pending").count(),
        "failed": Transaction.query.filter_by(status="failed").count(),
    }
    users = User.query.order_by(User.created.desc()).all()
    txns = Transaction.query.order_by(Transaction.searched_at.desc()).limit(100).all()
    return render_template("admin.html", stats=stats, users=users, txns=txns)

# ─── ERROR HANDLERS ──────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return render_template("500.html"), 500

# ─── INIT ────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_ENV") == "development"
    )
