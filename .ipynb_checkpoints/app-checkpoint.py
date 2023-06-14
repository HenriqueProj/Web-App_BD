#!/usr/bin/python3
from logging.config import dictConfig

import psycopg
from flask import flash
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from psycopg.rows import namedtuple_row
from psycopg_pool import ConnectionPool


# postgres://{user}:{password}@{hostname}:{port}/{database-name}
DATABASE_URL = "postgres://db:db@postgres/db"

pool = ConnectionPool(conninfo=DATABASE_URL)
# the pool starts connecting immediately.

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s:%(lineno)s - %(funcName)20s(): %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

app = Flask(__name__)
log = app.logger


@app.route("/", methods=("GET",))
def homepage():
    return render_template("index.html")

@app.route("/redirect", methods=("GET",))
def redirect_page():
    option = request.args.get('option')
    if option == 'list_products':
        return redirect("/products")
    # Add more conditions for other options if needed
    elif option == 'list_customers':
        return redirect("/customers")
    else:
        return redirect("/")

@app.route("/products", methods=("GET",))
def list_products():
    """Show all products"""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            products = cur.execute(
                """
                SELECT name, description, price, SKU
                FROM product
                ORDER BY name;
                """,
                {},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(products)

    return render_template("list.html", type = "product", list = products)


@app.route("/products/<sku>/edit", methods=("GET", "POST"))
def edit_product(sku):
    """Edit Product name and description"""
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            product = cur.execute(
                """
                SELECT name, description, price, SKU
                FROM product
                WHERE SKU = %(sku)s;
                """,
                {"sku": sku},
            ).fetchone()
            log.debug(f"Found {cur.rowcount} rows.")

    if request.method == "POST":
        price = request.form["product_price"]
        description = request.form["product_description"]

        error = None

        if not price:
            error = "Price is required."
            if not price.isnumeric():
                error = "Price should be a number."

        if not description:
            error = "Description is required."
            if not description.isalpha():
                error = "Description should be a string."

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        UPDATE product
                        SET price = %(price)s,
                            description = %(description)s
                        WHERE SKU = %(sku)s;
                        """,
                        {"price": price ,"description": description, "sku": sku},
                    )
                conn.commit()
            return redirect(url_for("list_products"))

    return render_template("products/edit.html", product = product)


@app.route("/customers", methods=("GET",))
def list_customers():
    """Show all customers"""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            customers = cur.execute(
                """
                SELECT name, email, address, phone
                FROM customer
                ORDER BY name;
                """,
                {},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(customers)

    return render_template("list.html", type = "customer", list = customers)

@app.route("/customers/add", methods=("GET",))
def add_customer():
    return 1


@app.route("/delivery", methods=("GET",))
def list_unpaid_orders():
    """Show all products"""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            unpaid = cur.execute(
                """
                SELECT order_no, cust_no
                FROM orders
                WHERE order_no NOT IN 
                (SELECT order_no from pay)
                ORDER BY order_no;
                """,
                {},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    # API-like response is returned to clients that request JSON explicitly (e.g., fetch)
    if (
        request.accept_mimetypes["application/json"]
        and not request.accept_mimetypes["text/html"]
    ):
        return jsonify(orders)

    return render_template("list.html", type = "order", list = unpaid)


@app.route("/insert", methods=("GET", "POST"))
def select_cust_no():
    return render_template("insert.html", type = "order")

@app.route("/delivery/show", methods=("POST",))
def show_customer_orders():
    
    cust_no = request.form.get('cust_no_form')

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            orders = cur.execute(
                """
                SELECT order_no, cust_no
                FROM orders
                WHERE cust_no = %(cust_no)s
                AND order_no not in 
                (select order_no from pay)
                ORDER BY order_no;
                """,
                {"cust_no": cust_no},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    return render_template("list.html", type="order", list = orders)

@app.route("/delivery/<order_no>/pay", methods=("GET", "POST"))
def pay_delivery(order_no):
    
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            order = cur.execute(
                """
                SELECT order_no, cust_no
                FROM orders
                WHERE order_no = %(order_no)s;
                """,
                {"order_no": order_no},
            ).fetchone()
            log.debug(f"Found {cur.rowcount} rows.")
    
        with pool.connection() as conn:
            with conn.cursor(row_factory=namedtuple_row) as cur:
                cur.execute(
                    """
                    INSERT INTO pay VALUES (%(order_no)s, %(cust_no)s);
                    """,
                    {"order_no": order[0] ,"cust_no": order[1]},
                )
                conn.commit()

    return render_template("delivery/pay.html", order=order)