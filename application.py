from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    username = db.execute("SELECT username FROM users WHERE id=:id", id=session["user_id"])
    stocks = db.execute("SELECT symbol, shares AS total, SUM(shares) AS shares, name, price FROM portfolio WHERE username=:username GROUP BY symbol",
                        username = username[0]["username"])
    cash = db.execute("SELECT cash FROM users WHERE id =:id", id=session["user_id"])
    if not stocks:
        return render_template("index.html", cash=cash[0]["cash"])
    else:
        for stock in stocks:
            data = lookup(stock["symbol"])
            stock["price"]= data["price"]
            stock["total"]= stock["shares"] * data["price"]
        return render_template("index.html", values=stocks, cash=cash[0]["cash"])


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "GET":
        return render_template("buy.html")
    elif request.method == "POST":
        rows = lookup(request.form.get("stock"))
        cash = db.execute("SELECT cash FROM users where id=:id", id=session["user_id"])
        shares = request.form.get("shares")
        if not request.form.get("stock"):
            return apology("missing symbol")
        elif not request.form.get("shares"):
            return apology("missing shares")
        elif not rows:
            return apology("invalid symbol")
        elif shares.isdigit() is not True:
            return apology("invalid shares")
        price_n=rows["price"]
        total_p=float(shares)*price_n
        if cash[0]["cash"] < total_p:
            return apology("can't afford")
        else:
            username = db.execute("SELECT username FROM users WHERE id=:id", id=session["user_id"])
            db.execute("INSERT INTO portfolio (symbol, username, shares, price, name) VALUES(:symbol, :username, :shares, :price, :name)",
            symbol=rows["symbol"], name=rows["name"], username=username[0]["username"], price=rows["price"],  shares=request.form.get("shares"))
            cash = cash[0]["cash"] - total_p
            db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=session["user_id"])
            flash('Bought!')
            return redirect(url_for("index"))


@app.route("/history")
@login_required
def history():
    username=db.execute("SELECT username FROM users WHERE id=:id",
    id=session["user_id"])
    list = db.execute("SELECT shares, price, date, symbol FROM portfolio WHERE username=:username ORDER BY date DESC",
    username=username[0]["username"])
    return render_template("history.html", values=list)

    """Show history of transactions."""
    #return apology("TODO")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    elif request.method == "POST":
        if not request.form.get("quote"):
            return apology("missing symbol")
        else:
            quote = lookup(request.form.get("quote"))
        if quote == None:
            return apology("invalid symbol")
        else:
            return render_template("quoted.html", values=quote)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "GET":
        return render_template("register.html")
    elif request.method =="POST":
        if not request.form.get("name"):
            return apology("MISSING USERNAME")
        elif not request.form.get("password"):
            return apology("MISSING PASSWORD")
        elif request.form["password"] != request.form["password_check"]:
            return apology("passwords don't match")
        else:
            hash = pwd_context.hash(request.form.get("password"))
        user_id = db.execute("INSERT INTO users(username, hash) VALUES(:username, :hash)", username = request.form.get("name"), hash=hash )
        if not user_id:
            return apology("username taken")
        else:
            session["user_id"] = user_id
            flash('Registered!')
            return redirect(url_for("index"))



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "GET":
        return render_template("sell.html")
    elif request.method == "POST":
        if not request.form.get("mystocks"):
            return apology("missing symbol")
        elif not request.form.get("myshares"):
            return apology("missing shares")
        elif request.form.get("myshares").isdigit() is not True:
            return apology("invalid shares")
        else:
            username = db.execute("SELECT username FROM users WHERE id =:id", id=session["user_id"])
            row = db.execute("SELECT SUM(shares) AS total, symbol FROM portfolio WHERE username=:username and symbol=:symbol GROUP BY symbol",
            username=username[0]["username"], symbol=request.form.get("mystocks").upper())
        if not row:
            return apology("symbol not owned")
        elif row[0]["total"] < int(request.form.get("myshares")):
            return apology("too many shares")
        else:
            shares = - int(request.form.get("myshares"))
            cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
            price=lookup(row[0]["symbol"])
            username = db.execute("SELECT username FROM users WHERE id=:id", id=session["user_id"])
            new_cash = cash[0]["cash"] + (price["price"] * int(request.form.get("myshares")))
            db.execute("UPDATE users SET cash=:cash WHERE id =:id", cash =new_cash, id=session["user_id"])
            db.execute("INSERT INTO portfolio(symbol, price, shares, name, username) VALUES(:symbol, :price, :shares, :name, :username)",
            symbol=request.form.get("mystocks").upper(), price=price["price"], shares=shares, name=price["name"], username = username[0]["username"])
            flash('Sold!')
            return redirect(url_for("index"))
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method =="GET":
        return render_template("settings.html")
    if request.method =="POST":
        row = db.execute("SELECT hash FROM users WHERE id=:id", id=session["user_id"])
        if request.form["mypassword"] =="" or request.form["newpassword"] =="" or request.form["confpass"]=="":
            return apology("no empty fields")
        elif not pwd_context.verify(request.form.get("mypassword"), row[0]["hash"]):
            return apology("wrong password")
        elif request.form.get("newpassword") != request.form.get("confpass"):
            return apology("passwords don't match")
        else:
            db.execute("UPDATE users SET hash=:hash WHERE id=:id", hash=pwd_context.hash(request.form.get("newpassword")), id=session["user_id"])
            return redirect(url_for("index"))

    #return apology("TODO")







