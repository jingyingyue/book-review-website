import os, requests, json

from flask import Flask, session, redirect, url_for, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
	# check if user is logged in
	if "user" not in session:
		return redirect(url_for("login"))
	return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
	"""register a user"""

	if request.method=="POST":
		username = request.form.get("username")
		password = request.form.get("password")

		# check if username already exists
		if db.execute("SELECT * FROM users WHERE username=:username", {"username": username}).rowcount!=0:
			return render_template("register.html", message="Sorry, username already exists")

		else:
			# hash password
			password_hashed = generate_password_hash(password)

			# insert new user into database
			db.execute("INSERT INTO users (username, password_hashed) VALUES (:username, :password_hashed)",
						{"username": username, "password_hashed": password_hashed})
			db.commit()

			# redirect user to login page
			return redirect(url_for("login"))

	else:
		return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
	"""login a user"""

	if request.method=="POST":
		username = request.form.get("username")
		password = request.form.get("password")

		# check if user is a registered user
		user = db.execute("SELECT * FROM users WHERE username=:username", {"username": username}).fetchone()
		if user is None:
			return render_template("login.html", message="Not a registered user")

		# check if correct password was entered
		elif not check_password_hash(user[2], password):
			return render_template("login.html", message="Incorrect password")

		else:
			# put user in a session
			session["user"] = user

			# redirect user to search page
			return redirect(url_for("index"))

	else:
		return render_template("login.html")


@app.route("/logout")
def logout():
	"""logout a user"""

	# remove user from session
	session.clear()

	# redirect user to login page
	return redirect(url_for("login"))


@app.route("/search", methods=["POST"])
def search():
	"""search for book(s)"""

	# check if user is logged in
	if "user" not in session:
		return redirect(url_for("login"))

	else:
		# get possible matches
		search = request.form.get("search")
		results = db.execute("SELECT * FROM books WHERE isbn LIKE :search OR LOWER(title) LIKE :search OR LOWER(author) LIKE :search",
								{"search": "%"+search+"%"}).fetchall()

		# check for no matches
		if not results:
			return render_template("index.html", message="No matches, please try again")

		return render_template("search.html", results=results)


@app.route("/book/<string:isbn>", methods=["GET", "POST"])
def book(isbn):
	"""get information about and/or post reviews for a book"""

	# check if user is logged in
	if "user" not in session:
		return redirect(url_for("login"))

	else:
		# get book information
		book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn}).fetchone()

		# get goodreads book information
		res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "8b2A0RlMNsIDmSH8XxrszQ", "isbns": isbn})
		data = res.json()
		gr_info = data["books"][0]

		# post a review
		if request.method=="POST":
			user = session["user"]
			reviews = db.execute("SELECT reviews.*, users.username FROM reviews INNER JOIN users ON reviews.user_id=users.id WHERE book_id=:book_id ORDER BY timing DESC", {"book_id": book[0]})
			rating = request.form.get("rating")
			opinion = request.form.get("opinion")

			# check if user already reviewed this book
			if db.execute("SELECT * FROM reviews WHERE user_id=:user_id AND book_id=:book_id",
							{"user_id": user[0], "book_id": book[0]}).rowcount!=0:
				return render_template("book.html", book=book, gr_info=gr_info, reviews=reviews, message="You already reviewed this book")
			
			# check if user did not write opinion or give a rating
			if not rating or not opinion:
				return render_template("book.html", book=book, gr_info=gr_info, reviews=reviews, message="No opinion/rating given")

			# add review to database
			db.execute("INSERT INTO reviews (rating, opinion, user_id, book_id) VALUES (:rating, :opinion, :user_id, :book_id)",
						{"rating": float(rating), "opinion": opinion, "user_id": user[0], "book_id": book[0]})
			db.commit()

		# get updated reviews
		reviews = db.execute("SELECT reviews.*, users.username FROM reviews INNER JOIN users ON reviews.user_id=users.id WHERE book_id=:book_id ORDER BY timing DESC", {"book_id": book[0]})

		return render_template("book.html", book=book, gr_info=gr_info, reviews=reviews)


@app.route("/api/<string:isbn>")
def book_api(isbn):
	"""get information about a book as JSON object"""

	book = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn}).fetchone()

	# check if book exists
	if book is None:
		return jsonify({"error": "Invalid ISBN"}), 404

	else:
		# get goodreads book information
		res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "8b2A0RlMNsIDmSH8XxrszQ", "isbns": isbn})
		data = res.json()
		gr_info = data["books"][0]

		return jsonify({
				"title": book[2],
				"author": book[3],
				"year": book[4],
				"isbn": isbn,
				"review_count": gr_info["work_ratings_count"],
				"average_score": gr_info["average_rating"]
			})


@app.route("/api")
def api():
	"""instructions on how to use API"""
	
	# check if user is logged in
	if "user" not in session:
		return redirect(url_for("login"))
	return render_template("api.html")
