import os, csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# create an engine to manage connections to the database
engine = create_engine(os.getenv("DATABASE_URL"))

# create a 'scoped session' to keep different users' interactions with the database separate
db = scoped_session(sessionmaker(bind=engine))

# import books.csv into the database
f = open("books.csv")
reader = csv.reader(f)

for isbn, title, author, year in reader:
	db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
				{"isbn": isbn, "title": title, "author": author, "year": year})
	print(f"Added {title} by {author}")

db.commit()