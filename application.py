import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from flask_googlecharts import GoogleCharts
from flask_googlecharts import PieChart

from helpers import apology, login_required, lookup, usd

# Configure application

charts = GoogleCharts()
app = Flask(__name__)
#charts = GoogleCharts(app)
charts.init_app(app)

# Import pie chart and decalre in view

stocks_chart = PieChart("stocks_pie_chart", options={'title': 'Portfolio'})

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL(os.getenv("DATABASE_URL"))

# Create transaction table. 
                
db.execute("""CREATE TABLE IF NOT EXISTS transaction (username TEXT NOT NULL, stock_name TEXT NOT NULL, stock_symbol TEXT NOT NULL, stock_price NUMERIC NOT NULL, shares INTEGER NOT NULL, share_holding_value NUMERIC NOT NULL DEFAULT 10000.00 , type_of_transaction TEXT NOT NULL, time_of_transaction DATETIME NOT NULL)""")
                 

# Make sure API key is set
#if not os.environ.get("API_KEY"):
    #raise RuntimeError("API_KEY not set")

@app.route("/")
def main_page():
    return redirect("/login")

@app.route("/index")
@login_required
def index():
    
    """Show portfolio of stocks"""
    
    # Which stonks the user owns
    user_id=session["user_id"]
    username = (db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0])
    username = username.get('username')
    
     # The stocks the user owns
    users_stocks_symbol_dict = db.execute("SELECT stock_symbol FROM transaction WHERE username = :username GROUP BY stock_symbol HAVING SUM (shares) > 0", username=username)
    users_stocks_symbol = [li['stock_symbol'] for li in users_stocks_symbol_dict]
    
    # The name of shares the user owns 
    users_stocks_name_dict = db.execute("SELECT stock_name FROM transaction WHERE username = :username GROUP BY stock_symbol HAVING SUM (shares) > 0", username=username)
    users_stocks_name = [li['stock_name'] for li in users_stocks_name_dict]
    
    # Number of shares the user owns 
    users_stocks_shares_dict = db.execute("SELECT SUM (shares) FROM transaction WHERE username = :username GROUP BY stock_symbol HAVING SUM (shares) > 0", username=username)
    users_stocks_shares = [li['SUM (shares)'] for li in users_stocks_shares_dict]
    
    # Look up the most recent price of the stocks owned.
    
    #Look up the stocks current price. Use lookup function to get dictionary of values from API
    
    stock_prices_non_usd = []
    
    for stock in users_stocks_symbol:
        symbol_dict = lookup(stock)
        symbol_price = symbol_dict.get("price")
        stock_prices_non_usd.append(symbol_price)
    
    
    # Total Shares Value 
    total_shares_value = [a*b for a,b in zip(users_stocks_shares, stock_prices_non_usd)]
    
    # Zip variable of lists that I want to iterate over. 
    user_stock_info = zip(users_stocks_symbol,users_stocks_name,users_stocks_shares,stock_prices_non_usd,total_shares_value)
    
    
    # Total cash the user has
    user_cash_dict = (db.execute("SELECT cash from users WHERE username = :username", username=username)[0])
    user_cash = user_cash_dict.get('cash')
    
    # Portfolio Total 
    
    portfolio_total = sum(total_shares_value) + user_cash
    
    
    # Variables for PieChart
    pie_chart_data = (db.execute("SELECT stock_symbol FROM transaction WHERE username = :username GROUP BY stock_symbol HAVING SUM (shares) > 0", username=username))
    print ("pie_chart_data:",pie_chart_data)
    
    pie_list = {'Stock' : 'Share Holding'}
    
    i = 0
    for data in pie_chart_data:
        pie_list.update(({data['stock_symbol']:total_shares_value[i]}))
        i = i+1
    
    #print(pie_list)
    
    pie_list.update(user_cash_dict)
    #print(pie_list)
  
    #If user makes a purchase, return the bought page
    return render_template("bought.html",pie_list=pie_list,charts=charts,stocks_chart=stocks_chart,users_stocks_symbol=users_stocks_symbol,users_stocks_name=users_stocks_name, users_stocks_shares=users_stocks_shares, stock_prices_non_usd=stock_prices_non_usd, total_shares_value=total_shares_value, user_stock_info=user_stock_info, portfolio_total=portfolio_total, user_cash=user_cash)
    
    return apology("TODO")

    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    #If user requests buy page, take them to buy page
    if request.method == "GET":
        return render_template("buy.html")

    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("Missing Symbol", 400)

        # Ensure shares was submitted
        if not request.form.get("shares"):
            return apology("Missing shares", 400)

        # Check if shares is a positive integer

        shares_number = request.form.get("shares")

        shares_number_float = float(shares_number)
        if shares_number_float < 1:
            return apology("Please enter a whole number greater than or equal to 1", 400)

        try:
            shares_number_int = int(shares_number)

        except ValueError:
            return apology("Please enter a whole number", 400)

        else:

            #Use lookup function to get dictionary of values from API
            symbol_dict = lookup(request.form.get("symbol"))

            if symbol_dict is not None:
                #Look up the stocks current price
                symbol_price = usd(symbol_dict.get("price"))

                #User id
                user_id=session["user_id"]
                
                # Select how much cash the user currently has (will need to check if user has engouh cash to make a purchase)
                user_cash = (db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)[0])
                user_cash_value = user_cash.get('cash')
                
                # Total stock purchased
                total_purchase = shares_number_int*(symbol_dict.get("price"))
                
                if float(user_cash_value)<float(total_purchase): 
                    return apology("Can't afford", 400)
                
                else:

                #Get user username and insert into purchase table

                    username = (db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0])
                    username = username.get('username')
                    
                    # Get stock symbol
                    stock_name = symbol_dict.get("name")
                    
                    # Get stock symbol
                    symbol_symbol = symbol_dict.get("symbol")
                    
                    # Get stock price
                    symbol_price = symbol_dict.get("price")
                    
                    # Total stock purchased in USD
                    
                    share_holding_value = shares_number_int*(symbol_dict.get("price"))
                    
                    # Time of stock purchased 
                    time_of_transaction = datetime.now()
                    
                    #Add the stock as an bought (purchased item)
                    
                    type_of_transaction = "Bought"
                
                    # Insert username, stock_name, stock_symbol, stock_price, shares, total purchase and time bought
                    db.execute("INSERT INTO transaction (username, stock_name, stock_symbol, stock_price, shares, share_holding_value, type_of_transaction, time_of_transaction) VALUES (:username, :stock_name, :symbol_symbol, :symbol_price, :shares, :share_holding_value, :type_of_transaction, :time_of_transaction)", username=username, stock_name=stock_name, symbol_symbol=symbol_symbol, symbol_price=symbol_price, shares=shares_number_int, share_holding_value=share_holding_value, type_of_transaction=type_of_transaction, time_of_transaction=time_of_transaction)
                    
                    # When stock is purchased, deduct this from the users cash total 
                    user_cash_dict = (db.execute("SELECT cash from users WHERE username = :username", username=username)[0])
                    user_cash = user_cash_dict.get('cash')
                        # Update user cash to deduct purchased stock 
                        
                    user_cash = user_cash - (shares_number_int*(symbol_dict.get("price")))
                        
                        # Update user table 
                    
                    db.execute("UPDATE users SET cash = :cash WHERE username = :username", cash=user_cash, username=username)
                    
                    # Render the bought page by returning the index function. Redirect user to bought page to show them their purchases
                    return redirect("/index")
        
                    
            else:
                # If symbol does not exist return invalid symbol
                return apology("Invalid Symbol", 400)

    return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    if request.method == "GET": 
        
        user_id=session["user_id"]
        
        username = (db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0])
        username = username.get('username')
        
        symbol_list_dict= db.execute("SELECT stock_symbol FROM transaction WHERE username = :username", username=username)
        symbol = [stock_symbol['stock_symbol'] for stock_symbol in symbol_list_dict]

        shares_list_dict = db.execute("SELECT shares FROM transaction WHERE username = :username", username=username)
        shares = [shares['shares'] for shares in shares_list_dict]
        
        price_list_dict = db.execute("SELECT stock_price FROM transaction WHERE username = :username", username=username)
        price = [stock_price['stock_price'] for stock_price in price_list_dict]
        
        transacted_list_dict = db.execute("SELECT time_of_transaction FROM transaction WHERE username = :username", username=username)
        transacted = [time_of_transaction['time_of_transaction'] for time_of_transaction in transacted_list_dict]
        
        # Zip variable of lists that I want to iterate over. 
        user_history_info = zip(symbol,shares,price,transacted)
        
        #Look up the stocks current price. Use lookup function to get dictionary of values from API
        
        return render_template("history.html", symbol=symbol, shares=shares, price=price, transacted=transacted, user_history_info=user_history_info)
        
    else: 
        
        return apology("Currently working on this feature")


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/index")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    #If user requests quote page, take them to quote page
    if request.method == "GET":
        return render_template("quote.html")

    # Ensure symbol was submitted
    if not request.form.get("symbol"):
        return apology("Missing Symbol", 400)

    #If user submits the quote request
    if request.method == "POST":

        #Use lookup function to get dictionary of values from API
        symbol_dict = lookup(request.form.get("symbol"))

        if symbol_dict is not None:
            symbol_name = symbol_dict.get("name")
            symbol_price = usd(symbol_dict.get("price"))
            symbol_symbol = symbol_dict.get("symbol")

            return render_template("quoted.html", symbol_name=symbol_name, symbol_symbol=symbol_symbol, symbol_price=symbol_price)
        else:
            return apology("Invalid Symbol", 400)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""


    #If user requests registration page, take them to registration template
    if request.method == "GET":
        return render_template("register.html")

    #If user sumbits their username and passoword then
    if request.method == "POST":

        #password_hash=generate_password_hash((request.form.get("password")))

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Check if the username already exists in the database (check if sql query returns 1 row. If 1 row returned then already in db)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Check if username already exists.
        if len(rows) == 1:
            return apology("Username already exists", 403)

        else:
            #return apology("We are working on adding your name", 403)
            #Insert username into databse
            db.execute("INSERT INTO users (username, hash) VALUES (?,?)", request.form.get("username"), generate_password_hash((request.form.get("password"))))

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure confirmation password was submitted
        elif not request.form.get("password_confirmation"):
            return apology("passwords don't match", 403)
        
        # log user in using the log in fucntion 
        login()
        
        # Redirect user to home page
        return redirect("/index")

    # Redirect user to home page
    return redirect("/register")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
     #If user requests sell page, take them to sell template
    if request.method == "GET":
        
        # Create a list array of symbols that the user owns 
        
        # Which stonks the user owns
        user_id=session["user_id"]
        username = (db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0])
        username = username.get('username')
        
        # The number of shares the user owns
    
        users_stocks_symbol_dict = db.execute("SELECT stock_symbol FROM 'transaction' WHERE username = :username GROUP BY stock_symbol HAVING SUM (shares) > 0", username=username)
        users_stocks_symbol = [li['stock_symbol'] for li in users_stocks_symbol_dict]
        
        return render_template("sell.html",users_stocks_symbol=users_stocks_symbol)
        

    #If submits their stocks for sale
    if request.method == "POST":
        
        # Ensure shares was submitted
        if not request.form.get("shares"):
            return apology("Missing shares", 400)

        # Check if shares is a positive integer

        shares_number = request.form.get("shares")

        shares_number_float = float(shares_number)
        if shares_number_float < 1:
            return apology("Please enter a whole number greater than or equal to 1", 400)

        try:
            shares_number_int = int(shares_number)

        except ValueError:
            return apology("Please enter a whole number", 400)
            
        # Make shares number negative 
        
        shares_number_int = -(shares_number_int)
            
        # Insert into table the value of the sold shares 
        
        #Use lookup function to get dictionary of values from API
        symbol_dict = lookup(request.form.get("symbol"))
        print(symbol_dict)

        #User id
        user_id=session["user_id"]
        
        # Select how much cash the user currently has (will need to check if user has engouh cash to make a purchase)
        user_cash = (db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)[0])
        user_cash_value = user_cash.get('cash')
        
        # Total stock sold
        total_sale = shares_number_int*(symbol_dict.get("price"))

        #Get user username and insert into purchase table

        username = (db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)[0])
        username = username.get('username')
        
        # Get stock symbol
        stock_name = symbol_dict.get("name")
        print(stock_name)
        
        # Get stock symbol
        symbol_symbol = symbol_dict.get("symbol")
        print(symbol_symbol)
        
        # Get stock price
        symbol_price = symbol_dict.get("price")
        print(symbol_price)
        
        # Total stock purchased in USD
        share_holding_value = shares_number_int*(symbol_dict.get("price"))
        print(share_holding_value)
        
        # Time of stock purchased 
        time_of_transaction = datetime.now()
        
        #Add the stock as an owned(purchased item)
        
        type_of_transaction = "Sold"
    
        # Insert username, stock_name, stock_symbol, stock_price, shares, total purchase and time bought
        db.execute("INSERT INTO 'transaction' (username, stock_name, stock_symbol, stock_price, shares, share_holding_value, type_of_transaction, time_of_transaction) VALUES (:username, :stock_name, :symbol_symbol, :symbol_price, :shares, :share_holding_value, :type_of_transaction, :time_of_transaction)", username=username, stock_name=stock_name, symbol_symbol=symbol_symbol, symbol_price=symbol_price, shares=shares_number_int, share_holding_value=share_holding_value, type_of_transaction=type_of_transaction, time_of_transaction=time_of_transaction)
        
        # When stock is sold, add this from the users cash total 
        user_cash_dict = (db.execute("SELECT cash from users WHERE username = :username", username=username)[0])
        user_cash = user_cash_dict.get('cash')
            # Update user cash to deduct purchased stock 
            
        user_cash = user_cash - (shares_number_int*(symbol_dict.get("price")))
            
            # Update user table 
        
        db.execute("UPDATE users SET cash = :cash WHERE username = :username", cash=user_cash, username=username)
        
        # Render the bought page by returning the index function. Redirect user to bought page to show them their purchases
        return redirect("/index")
    
    
        return render_template("bought.html")
        
        return apology("Currently working on this feature")
        
    else:
    
        return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
