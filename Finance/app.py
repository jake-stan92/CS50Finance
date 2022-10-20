import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    newDictList = []
    newDict = {}

    stocks = db.execute("SELECT product, symbol, sum(amount) FROM purchases WHERE id=? GROUP BY product", session["user_id"])

    # check to see if stocks are empty.. if so break

    for stock in stocks:
        if not stocks:
            print('empty')
            break

    # loop stocks db to add results to a new list for ease of access (struggled with count function previously)
    for i in range(len(stocks)):
        product = stocks[i]["product"]
        symbol = stocks[i]["symbol"]
        count = stocks[i]["sum(amount)"]
        newDict["product"] = product
        newDict["symbol"] = symbol
        newDict["amount"] = count

        result = lookup(symbol)
        price = result["price"]
        newDict["price"] = price
        totalValue = price * count
        newDict["totalValue"] = totalValue
        

        # exclude 0 total stocks (owned before but now sold)
        if count != 0:
            newDictList.append(newDict)
            newDict = {}

    # current cash

    currentCashList = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
    currentCash = currentCashList[0]["cash"]
    #usdCurrentCash = usd(currentCash)

    # sum of total Value column

    total = 0

    for stock in newDictList:
        value = float(stock["totalValue"])
        total += float(value)

    # total cash flow

    totalCashFlow = total + currentCash

    return render_template("index.html", stocks=stocks, newDictList=newDictList, currentCash=currentCash, totalCashFlow=totalCashFlow)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # Perform Validation using request.form.get
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        if not request.form.get("shares").isdigit():
            return apology("must provide a whole number", 400)

        if int(request.form.get("shares")) < 1:
            return apology("must provide a positive value", 400)

        # complete lookup on users entered symbol
        userSymbol = request.form.get("symbol")
        global results
        results = lookup(userSymbol)

        # check to see if lookup returns nothing
        if not results:
            return apology("must provide a correct symbol", 400)

        name = results["name"]
        price = results["price"]

        global dollarPrice
        dollarPrice = usd(price)

        symbol = results["symbol"]
        global numShares
        numShares = int(request.form.get("shares"))

        global totalPrice
        totalPrice = float(results["price"]) * float(request.form.get("shares"))
        # usdTotalPrice = usd(totalPrice)

        global dollarTotalPrice
        dollarTotalPrice = usd(totalPrice)

        currentCashList = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
        currentCash = currentCashList[0]["cash"]

        global dollarCurrentCash
        dollarCurrentCash = usd(currentCash)

        name = results["name"]
        symbol = results["symbol"]

        if int(currentCash) > totalPrice:

            remainingBalance = currentCash - totalPrice
            dollarRemainingBalance = usd(remainingBalance)

            # Deduct cash from  users DB
            db.execute("UPDATE users SET cash=? WHERE id=?", remainingBalance, session["user_id"])

            # Update purchases DB with purchase
            usernameGet = db.execute("SELECT username FROM users WHERE id=?", session["user_id"])
            username = usernameGet[0]["username"]

            # add date and time to transaction
            now = datetime.now()
            transTime = now.strftime("%d/%m/%Y %H:%M:%S")

            db.execute("INSERT INTO purchases (id, username, totalPrice, product, amount, symbol, transactionType, dateTime) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                       session["user_id"], username, totalPrice, name, numShares, symbol, "BUY", transTime)

            return render_template("success.html", dollarRemainingBalance=dollarRemainingBalance, name=name, dollarTotalPrice=dollarTotalPrice, numShares=numShares, symbol=symbol)

        else:
            return render_template("failure.html", dollarCurrentCash=dollarCurrentCash, dollarTotalPrice=dollarTotalPrice)

    else:
        return render_template("buy.html")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit more money,, min 50 ,, max 1000"""

    if request.method == "POST":
        # perform validation

        deposit = request.form.get("deposit")

        if not deposit.isdigit():
            return apology("must provide a whole number", 400)

        if int(deposit) < 1:
            return apology("must provide a positive value", 400)

        if int(deposit) < 50 or int(deposit) > 1000:
            return apology("must provide a value between 50 and 1000", 400)

        # get current cash

        currentCashList = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
        currentCash = currentCashList[0]["cash"]

        # update new cash balance

        remainingBalance = currentCash + int(deposit)

        # update cash in users DB

        db.execute("UPDATE users SET cash=? WHERE id=?", remainingBalance, session["user_id"])

        # working, to update total, could add into trans history

        return redirect("/deposit")

    else:
        return render_template("deposit.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute(
        "SELECT product, symbol, amount, totalPrice, transactionType, dateTime FROM purchases WHERE id=?", session["user_id"])

    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # POST use lookup function and display results from form

    if request.method == "POST":

        # Perform Validation using request.form.get
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # complete lookup on users entered symbol
        userSymbol = request.form.get("symbol")
        results = lookup(userSymbol)

        # check to see if lookup returns nothing
        if not results:
            return apology("must provide a correct symbol", 400)

        name = results["name"]
        symbol = results["symbol"]
        price = results["price"]
        dollarPrice = usd(price)

        # direct user to quoted page which will display the quote for given symbol
        return render_template("quoted.html", name=name, dollarPrice=dollarPrice, symbol=symbol)

    # GET should display form to request stock quote
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # error check as per login above
        # empty fields are handled by required="true"

        if not request.form.get("username") or not request.form.get("password"):
            return apology("One or more fields are empty", 400)

        # Query database to see if username exists
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) != 0:
            return apology("This username already exists", 400)

        # Check to see if entered passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match")

        # Add new user to database
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password)
        newUserId = db.execute("SELECT id FROM users WHERE username = ?", username)

        # Remember which user has logged in
        session["user_id"] = newUserId[0]["id"]

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    newDictList = []
    newDict = {}

    stocks = db.execute("SELECT product, symbol, sum(amount) FROM purchases WHERE id=? GROUP BY product", session["user_id"])

    # loop stocks db to add results to a new list for ease of access (struggled with count function previously)

    for i in range(len(stocks)):
        product = stocks[i]["product"]
        symbol = stocks[i]["symbol"]
        count = stocks[i]["sum(amount)"]
        newDict["product"] = product
        newDict["symbol"] = symbol
        newDict["amount"] = count

    # exclude 0 total stocks (owned before but now sold)

        if count != 0:
            newDictList.append(newDict)
            newDict = {}

    # loop length of owned stocks and add symbol to newly created list
    ownedStocksSymbols = []

    for i in range(len(newDictList)):

        sym = newDictList[i]["symbol"]
        ownedStocksSymbols.append(sym)

     # Process POST request

    if request.method == "POST":

        # validate form entries

        stockEntry = request.form.get("symbol").upper()
        sharesEntry = request.form.get("shares")

        # empty entry

        if not stockEntry or not sharesEntry:
            return apology("Please enter a stock symbol or # of shares to sell", 403)

        # no stocks owned of symbol entry

        if stockEntry.upper() not in ownedStocksSymbols:
            return apology("You do not own any of this stock")

        # not enough of stock entered stock to sell

        # use newDictList to perform lookup

        for i in range(len(newDictList)):
            if newDictList[i]["symbol"] == stockEntry:
                global ownedStock
                ownedStock = int(newDictList[i]["amount"])

        if int(sharesEntry) > ownedStock:
            return apology("You dont own enough of this stock to sell that much")

        # alter cash on users table

        results = lookup(stockEntry)
        price = results["price"]

        currentCashList = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
        currentCash = currentCashList[0]["cash"]
        totalSalePrice = float(sharesEntry) * float(price)

        remainingBalance = currentCash + totalSalePrice

        # convert + share number to negative to reflect in db
        deduction = int(-abs(int(sharesEntry)))

        # add cash in users DB
        db.execute("UPDATE users SET cash=? WHERE id=?", remainingBalance, session["user_id"])

        # reflect changes in purchases table

        name = results["name"]
        usernameGet = db.execute("SELECT username FROM users WHERE id=?", session["user_id"])
        username = usernameGet[0]["username"]

        # add date and time to transaction
        now = datetime.now()
        transTime = now.strftime("%d/%m/%Y %H:%M:%S")

        db.execute("INSERT INTO purchases (id, username, totalPrice, product, amount, symbol, transactionType, dateTime) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                   session["user_id"], username, totalSalePrice, name, deduction, stockEntry, "SELL", transTime)

        return redirect("/")

    else:

        # Display how much of each stock the logged in person owns

        return render_template("sell.html", stocks=stocks, newDictList=newDictList, ownedStocksSymbols=ownedStocksSymbols)
