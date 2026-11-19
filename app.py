import os
from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, db

from agents.retention_agent import RetentionAgent
from agents.support_chatbot import SupportChatbot
from services.auth_service import authenticate_user, register_user
from services.dnn_model import DNNChurnPredictor

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "churn-agent-dev-secret-change-in-production")

# ==============================
# FIREBASE INIT
# ==============================
FIREBASE_CREDENTIALS = os.environ.get(
    "FIREBASE_CREDENTIALS",
    "customer-churn-1cb40-firebase-adminsdk-fbsvc-30f105638a.json",
)
FIREBASE_DB_URL = os.environ.get(
    "FIREBASE_DB_URL",
    "https://customer-churn-1cb40-default-rtdb.firebaseio.com/",
)

if os.path.exists(FIREBASE_CREDENTIALS):
    cred = credentials.Certificate(FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
else:
    raise FileNotFoundError(
        "Firebase credentials not found. Put your Firebase service-account JSON "
        "in the project folder or set FIREBASE_CREDENTIALS to its path."
    )

# ==============================
# LOAD MODEL & AGENT
# ==============================
model = DNNChurnPredictor()
retention_agent = RetentionAgent(model)
support_chatbot = SupportChatbot()


@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# ==============================
# AUTH ROUTES
# ==============================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user"):
        return redirect(url_for("predict"))

    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        ok, result = register_user(db, name, email, password)
        if not ok:
            flash(result, "error")
            return render_template("signup.html")

        user_record = db.reference(f"users/{result}").get()
        session["user"] = {
            "uid": result,
            "name": user_record.get("name", name),
            "email": user_record.get("email", email.strip().lower()),
        }
        flash("Account created successfully. Welcome!", "success")
        return redirect(url_for("predict"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("predict"))

    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        ok, result = authenticate_user(db, email, password)
        if not ok:
            flash(result, "error")
            return render_template("login.html", next_url=next_url)

        session["user"] = result
        flash(f"Welcome back, {result['name']}!", "success")

        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("predict"))

    return render_template("login.html", next_url=next_url)


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("last_prediction", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ==============================
# APP ROUTES
# ==============================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    result = None
    retention_plan = None

    if request.method == "POST":
        customer = {
            "credit_score": request.form["credit_score"],
            "geography": request.form["geography"],
            "gender": request.form["gender"],
            "age": request.form["age"],
            "tenure": request.form["tenure"],
            "balance": request.form["balance"],
            "num_products": request.form["num_products"],
            "has_card": request.form["has_card"],
            "is_active": request.form["is_active"],
            "salary": request.form["salary"],
        }

        trace = retention_agent.run(customer)
        pred = trace["prediction"]
        result = pred["result_text"]
        retention_plan = trace

        session["last_prediction"] = {
            "prediction": pred,
            "retention": trace["retention"],
        }

        ref = db.reference("predictions")
        payload = retention_agent.to_firebase_payload(customer, trace)
        payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = session.get("user", {})
        payload["user_uid"] = user.get("uid")
        payload["user_email"] = user.get("email")
        ref.push(payload)

    return render_template(
        "predict.html",
        result=result,
        retention_plan=retention_plan,
    )


@app.route("/chat")
@login_required
def chat():
    return render_template(
        "chat.html",
        has_last_prediction=bool(session.get("last_prediction")),
    )


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    ctx = session.get("last_prediction")
    reply = support_chatbot.reply(message, context=ctx)
    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)
