from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import os
import re


app = Flask(__name__)


# ==========================================
# SECRET KEY
# ==========================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "spendtrack-development-secret-key"
)


# ==========================================
# DATABASE
# ==========================================

def get_db():

    conn = sqlite3.connect("expense_tracker.db")

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================
# LOGIN CHECK
# ==========================================

def is_logged_in():

    return "user_id" in session


# ==========================================
# HOME / LOGIN
# ==========================================

@app.route("/")
def login():

    if is_logged_in():
        return redirect("/dashboard")

    return render_template("login.html")


# ==========================================
# REGISTER
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        # Name validation

        if len(name) < 2:

            return "Name must contain at least 2 characters."


        # Email validation

        email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if not re.match(email_pattern, email):

            return "Please enter a valid email address."


        # Password validation

        if len(password) < 6:

            return "Password must contain at least 6 characters."


        # Hash password

        hashed_password = generate_password_hash(
            password
        )


        conn = get_db()


        try:

            conn.execute("""
                INSERT INTO users
                (name, email, password)
                VALUES (?, ?, ?)
            """, (
                name,
                email,
                hashed_password
            ))


            conn.commit()

            conn.close()


            return redirect("/")


        except sqlite3.IntegrityError:

            conn.close()

            return "Email already registered!"


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["POST"])
def login_user():

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )


    conn = get_db()


    user = conn.execute("""
        SELECT *
        FROM users
        WHERE email = ?
    """, (
        email,
    )).fetchone()


    conn.close()


    if user and check_password_hash(
        user["password"],
        password
    ):

        session.clear()

        session["user_id"] = user["id"]

        session["user_name"] = user["name"]

        return redirect("/dashboard")


    return "Invalid email or password!"


# ==========================================
# DASHBOARD
# ==========================================

@app.route("/dashboard")
def dashboard():

    if not is_logged_in():

        return redirect("/")


    user_id = session["user_id"]


    conn = get_db()


    # --------------------------------------
    # ALL EXPENSES
    # --------------------------------------

    expenses = conn.execute("""
        SELECT *
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
    """, (
        user_id,
    )).fetchall()


    # --------------------------------------
    # TOTAL EXPENSE
    # --------------------------------------

    total = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
    """, (
        user_id,
    )).fetchone()[0]


    # --------------------------------------
    # TOTAL TRANSACTIONS
    # --------------------------------------

    expense_count = conn.execute("""
        SELECT COUNT(*)
        FROM expenses
        WHERE user_id = ?
    """, (
        user_id,
    )).fetchone()[0]


    # --------------------------------------
    # THIS MONTH
    # --------------------------------------

    current_month = datetime.now().strftime(
        "%Y-%m"
    )


    monthly_total = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND date LIKE ?
    """, (
        user_id,
        current_month + "%"
    )).fetchone()[0]


    # --------------------------------------
    # CATEGORY-WISE EXPENSE
    # --------------------------------------

    category_data = conn.execute("""
        SELECT
            category,
            SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
    """, (
        user_id,
    )).fetchall()


    # --------------------------------------
    # CHART DATA
    # --------------------------------------

    category_names = [

        row["category"]

        for row in category_data

    ]


    category_amounts = [

        row["total"]

        for row in category_data

    ]


    conn.close()


    return render_template(
        "dashboard.html",

        expenses=expenses,

        total=total,

        monthly_total=monthly_total,

        expense_count=expense_count,

        category_data=category_data,

        category_names=category_names,

        category_amounts=category_amounts,

        name=session["user_name"]
    )


# ==========================================
# VIEW / SEARCH / FILTER EXPENSES
# ==========================================

@app.route("/expenses")
def expenses():

    if not is_logged_in():

        return redirect("/")


    search = request.args.get(
        "search",
        ""
    ).strip()


    category = request.args.get(
        "category",
        ""
    ).strip()


    month = request.args.get(
        "month",
        ""
    ).strip()


    conn = get_db()


    query = """
        SELECT *
        FROM expenses
        WHERE user_id = ?
    """


    params = [
        session["user_id"]
    ]


    # Search

    if search:

        query += """
            AND title LIKE ?
        """

        params.append(
            "%" + search + "%"
        )


    # Category filter

    if category:

        query += """
            AND category = ?
        """

        params.append(category)


    # Month filter

    if month:

        query += """
            AND date LIKE ?
        """

        params.append(
            month + "%"
        )


    query += """
        ORDER BY date DESC, id DESC
    """


    expenses = conn.execute(
        query,
        params
    ).fetchall()


    conn.close()


    return render_template(
        "expenses.html",

        expenses=expenses,

        search=search,

        category=category,

        month=month
    )


# ==========================================
# ADD EXPENSE
# ==========================================

@app.route(
    "/add-expense",
    methods=["GET", "POST"]
)
def add_expense():

    if not is_logged_in():

        return redirect("/")


    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()


        amount_text = request.form.get(
            "amount",
            ""
        ).strip()


        category = request.form.get(
            "category",
            ""
        ).strip()


        date = request.form.get(
            "date",
            ""
        ).strip()


        # ----------------------------------
        # TITLE VALIDATION
        # ----------------------------------

        if not title:

            return "Expense name is required."


        if len(title) > 100:

            return "Expense name is too long."


        # ----------------------------------
        # AMOUNT VALIDATION
        # ----------------------------------

        try:

            amount = float(amount_text)

        except ValueError:

            return "Please enter a valid amount."


        if amount <= 0:

            return "Amount must be greater than 0."


        # ----------------------------------
        # CATEGORY VALIDATION
        # ----------------------------------

        allowed_categories = [

            "Food",
            "Travel",
            "Shopping",
            "Bills",
            "Education",
            "Entertainment",
            "Health",
            "Other"

        ]


        if category not in allowed_categories:

            return "Invalid category."


        # ----------------------------------
        # DATE VALIDATION
        # ----------------------------------

        try:

            datetime.strptime(
                date,
                "%Y-%m-%d"
            )

        except ValueError:

            return "Please enter a valid date."


        # ----------------------------------
        # SAVE
        # ----------------------------------

        conn = get_db()


        conn.execute("""
            INSERT INTO expenses
            (
                user_id,
                title,
                amount,
                category,
                date
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            amount,
            category,
            date
        ))


        conn.commit()

        conn.close()


        return redirect("/dashboard")


    return render_template(
        "add_expense.html"
    )


# ==========================================
# EDIT EXPENSE
# ==========================================

@app.route(
    "/edit/<int:expense_id>",
    methods=["GET", "POST"]
)
def edit_expense(expense_id):

    if not is_logged_in():

        return redirect("/")


    conn = get_db()


    # Important:
    # user_id condition means one user
    # cannot edit another user's expense.

    expense = conn.execute("""
        SELECT *
        FROM expenses
        WHERE id = ?
        AND user_id = ?
    """, (
        expense_id,
        session["user_id"]
    )).fetchone()


    if expense is None:

        conn.close()

        return "Expense not found."


    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()


        amount_text = request.form.get(
            "amount",
            ""
        ).strip()


        category = request.form.get(
            "category",
            ""
        ).strip()


        date = request.form.get(
            "date",
            ""
        ).strip()


        # ----------------------------------
        # VALIDATE TITLE
        # ----------------------------------

        if not title:

            conn.close()

            return "Expense name is required."


        if len(title) > 100:

            conn.close()

            return "Expense name is too long."


        # ----------------------------------
        # VALIDATE AMOUNT
        # ----------------------------------

        try:

            amount = float(amount_text)

        except ValueError:

            conn.close()

            return "Please enter a valid amount."


        if amount <= 0:

            conn.close()

            return "Amount must be greater than 0."


        # ----------------------------------
        # VALIDATE CATEGORY
        # ----------------------------------

        allowed_categories = [

            "Food",
            "Travel",
            "Shopping",
            "Bills",
            "Education",
            "Entertainment",
            "Health",
            "Other"

        ]


        if category not in allowed_categories:

            conn.close()

            return "Invalid category."


        # ----------------------------------
        # VALIDATE DATE
        # ----------------------------------

        try:

            datetime.strptime(
                date,
                "%Y-%m-%d"
            )

        except ValueError:

            conn.close()

            return "Please enter a valid date."


        # ----------------------------------
        # UPDATE
        # ----------------------------------

        conn.execute("""
            UPDATE expenses

            SET
                title = ?,
                amount = ?,
                category = ?,
                date = ?

            WHERE id = ?
            AND user_id = ?
        """, (
            title,
            amount,
            category,
            date,
            expense_id,
            session["user_id"]
        ))


        conn.commit()

        conn.close()


        return redirect("/expenses")


    conn.close()


    return render_template(
        "edit_expense.html",
        expense=expense
    )


# ==========================================
# DELETE EXPENSE
# ==========================================

@app.route(
    "/delete/<int:expense_id>"
)
def delete_expense(expense_id):

    if not is_logged_in():

        return redirect("/")


    conn = get_db()


    # User can delete only their own expense.

    conn.execute("""
        DELETE FROM expenses

        WHERE id = ?

        AND user_id = ?
    """, (
        expense_id,
        session["user_id"]
    ))


    conn.commit()

    conn.close()


    return redirect("/dashboard")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run()