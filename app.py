from flask import Flask, render_template_string, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
import stripe
import os
import io

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_this_secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# -------- MODELS --------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(200))
    subscription = db.Column(db.String(50), default="free")

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client = db.Column(db.String(150))
    amount = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------- ROUTES --------

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect("/login")

    return render_template_string("""
    <h2>Inscription</h2>
    <form method="POST">
    <input name="email" placeholder="Email"><br>
    <input name="password" type="password" placeholder="Mot de passe"><br>
    <button>S'inscrire</button>
    </form>
    """)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect("/dashboard")

    return render_template_string("""
    <h2>Connexion</h2>
    <form method="POST">
    <input name="email" placeholder="Email"><br>
    <input name="password" type="password" placeholder="Mot de passe"><br>
    <button>Connexion</button>
    </form>
    <a href="/register">Créer compte</a>
    """)

@app.route("/dashboard", methods=["GET","POST"])
@login_required
def dashboard():
    if request.method == "POST":
        invoice = Invoice(
            client=request.form["client"],
            amount=request.form["amount"],
            user_id=current_user.id
        )
        db.session.add(invoice)
        db.session.commit()

    invoices = Invoice.query.filter_by(user_id=current_user.id).all()

    html = """
    <h2>Dashboard</h2>
    <form method="POST">
    <input name="client" placeholder="Client">
    <input name="amount" type="number" placeholder="Montant">
    <button>Créer facture</button>
    </form>
    <hr>
    """

    for inv in invoices:
        html += f"""
        <p>{inv.client} - {inv.amount} € 
        <a href='/invoice/{inv.id}/pdf'>PDF</a></p>
        """

    html += """
    <hr>
    <a href="/subscribe">Passer en Premium</a><br>
    <a href="/logout">Déconnexion</a>
    """

    return render_template_string(html)

@app.route("/invoice/<int:id>/pdf")
@login_required
def pdf(id):
    invoice = Invoice.query.get(id)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 800, f"Facture pour {invoice.client}")
    p.drawString(100, 780, f"Montant: {invoice.amount} €")
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="facture.pdf")

@app.route("/subscribe")
@login_required
def subscribe():
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price": os.getenv("STRIPE_PRICE_ID"),
            "quantity": 1
        }],
        success_url="https://yourdomain.com/dashboard",
        cancel_url="https://yourdomain.com/dashboard",
    )
    return redirect(session.url)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()
