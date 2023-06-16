#!/usr/bin/python3
from logging.config import dictConfig

import re
import datetime
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
app.secret_key = "BD-E3-L14-F49"
log = app.logger


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Example authentication logic
        if username and password:
            return redirect(url_for("homepage"))
        else:
            error_message = "Invalid username or password"
            return render_template("login.html", error=error_message)

    return render_template("login.html")


@app.route("/home", methods=("GET",))
def homepage():
    return render_template("index.html")


@app.route("/redirect", methods=("GET",))
def redirect_page():
    """Redirects the dropdown list to it's correspondent page"""

    option = request.args.get("option")
    if option == "list_products":
        return redirect("/products")
    # Add more conditions for other options if needed
    elif option == "list_products_edit":
        return redirect("/products/edit")
    elif option == "list_products_insert_remove":
        return redirect("/products/insert_remove")
    elif option == "list_customers":
        return redirect("/customers")
    elif option == "list_suppliers":
        return redirect("/suppliers")
    elif option == "list_product_make_order":
        return redirect(url_for("get_cust_no_for_order", purpose="make_order"))
    elif option == "pay_order":
        return redirect("/insert")
    else:
        return redirect("/")


@app.route("/products/<purpose>", methods=("GET", "POST"))
def list_products(purpose):
    """
    Show all products
    It can have 3 purposes:
       -> edit
       -> insert_remove
       -> edit
    """

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

    # type indicates it's going to list products
    return render_template("list.html", type="product", list=products, purpose=purpose)


@app.route("/suppliers", methods=("GET",))
def list_suppliers():
    """Show all the suppliers, alphabetically."""

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            suppliers = cur.execute(
                """
                SELECT TIN, name, address, date
                FROM supplier
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
        return jsonify(suppliers)

    return render_template("list.html", type="supplier", list=suppliers)


@app.route("/customers", methods=("GET",))
def list_customers():
    """
    Show all customers
    ignoring customers who
    had their attributes removed
    from the Data Base
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            customers = cur.execute(
                """
                SELECT name, email, address, phone, cust_no
                FROM customer
                WHERE name NOT LIKE 'NAME%%'
                AND email NOT LIKE 'X%%'
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

    return render_template("list.html", type="customer", list=customers)


#         a) Registar e remover produtos e fornecedores


@app.route("/supplier/supplier_add", methods=("GET", "POST"))
def add_supplier():
    """Add a new supplier."""

    if request.method == "POST":
        # read input fields
        TIN = request.form["TIN"]
        name = request.form["supplier_name"]
        address = request.form["address"]
        SKU = request.form["SKU"]
        date = request.form["date"]

        error = None

        # check adress format: Street street number XXXX-XXX City
        address_pattern = r"^[\w\s]+(?: \d+)? \d{4}-\d{3} [\w\s]+$"
        if not re.match(address_pattern, address) and address:
            error = "Adress format is invalid"

        if not TIN:
            error = "TIN is required."

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                            INSERT INTO supplier (TIN, name, address, SKU, date)
                            VALUES (%(TIN)s, %(name)s, %(address)s, %(SKU)s, %(date)s);
                            """,
                        {
                            "TIN": TIN,
                            "name": name or None,
                            "address": address or None,
                            "SKU": SKU or None,
                            "date": date or None,
                        },
                    )
                conn.commit()
                return redirect(url_for("list_suppliers"))

    return render_template("add_supplier.html", supplier={})


@app.route("/supplier/<supplier_number>/remove", methods=("POST",))
def supplier_remove(supplier_number):
    """
    Delete the supplier
    and the deliverys associated
    to him
    """

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                DELETE FROM delivery
                WHERE TIN=%(supplier_number)s;
                """,
                {"supplier_number": supplier_number},
            )
            cur.execute(
                """
                DELETE FROM supplier
                WHERE TIN=%(supplier_number)s;
                """,
                {"supplier_number": supplier_number},
            )
        conn.commit()
    return redirect(url_for("list_suppliers"))


@app.route("/product/product_add", methods=("GET", "POST"))
def add_product():
    """Add a new product."""

    if request.method == "POST":
        SKU = request.form["SKU"]
        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        EAN = request.form["EAN"]

        error = None
        if not name:
            error = "Name is required."

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                            INSERT INTO product (SKU,name, description, price, EAN)
                            VALUES (%(SKU)s,%(name)s, %(description)s, %(price)s, %(EAN)s);
                            """,
                        {
                            "SKU": SKU,
                            "name": name,
                            "description": description or None,
                            "price": price,
                            "EAN": EAN or None,
                        },
                    )
                conn.commit()
                return redirect(url_for("list_products", purpose='insert_remove'))

    return render_template("add_product.html", product={})


@app.route("/product/<SKU>/remove", methods=("POST", "GET"))
def product_remove(SKU):
    """
    Delete the product,
    set SKU of suppliers that delivered that product to null,
    remove contains from orders that have that product
    and finally remove product from table product
    For simplicity, the order isn't deleted if
    contains doesn't appear in contains after a product is removed,
    so it doesn't cause problems to other tables
    """
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                UPDATE supplier
                SET SKU = NULL
                WHERE SKU = %(SKU)s;
                """,
                {"SKU": SKU},
            )
            cur.execute(
                """
                DELETE FROM contains
                WHERE SKU = %(SKU)s;
                """,
                {"SKU": SKU},
            )

            cur.execute(
                """
                DELETE FROM product
                WHERE SKU = %(SKU)s;
                """,
                {"SKU": SKU},
            )
        conn.commit()
    return redirect(url_for("list_products", purpose="insert_remove"))


#            b) Alterar preços de produtos e respectivas descrições


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
        # read input fields
        price = request.form["product_price"]
        description = request.form["product_description"]

        error = None

        if not price:
            error = "Price is required."
            if not price.isnumeric():
                error = "Price should be a number."

        if not(not description.isalpha() or not description.isdigit()) and description:
            error = "Description should be a string."

        if error is not None:
            flash(error)
        else:
            # update price and description
            with pool.connection() as conn:
                with conn.cursor(row_factory=namedtuple_row) as cur:
                    cur.execute(
                        """
                        UPDATE product
                        SET price = %(price)s,
                            description = %(description)s
                        WHERE SKU = %(sku)s;
                        """,
                        {"price": price, "description": description, "sku": sku},
                    )
                conn.commit()
            return redirect(url_for("list_products", purpose="edit"))

    return render_template("edit.html", product=product)


#               c) Registar e remover clientes


@app.route("/customers/add_customer", methods=("GET", "POST"))
def add_customer():
    """Add a new customer."""

    if request.method == "POST":
        # read input fields
        name = request.form["name"]
        email = request.form["email"]
        address = request.form["address"]
        phone = request.form["phone"]

        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Get the maximum cust_no
                cur.execute("SELECT MAX(cust_no) FROM customer")
                max_cust_no = cur.fetchone()[0]

                if max_cust_no is None:
                    cust_no = 1
                else:
                    # increment cust_no for new customer
                    cust_no = max_cust_no + 1

        error = None

        # Verifying address format: Street Street_no XXXX-XXX City
        address_pattern = r"^[\w\s]+(?: \d+)? \d{4}-\d{3} [\w\s]+$"
        if not re.match(address_pattern, address) and address:
            error = "Adress format is invalid"

        # check if phone number has 9 numeric digits
        if (not phone.isdigit() or len(phone) != 9) and phone:
            error = "Phone number must have 9 numeric digits"

        if error is not None:
            flash(error)
        else:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO customer (cust_no, name, email, phone, address)
                        VALUES (%(cust_no)s, %(name)s, %(email)s, %(phone)s, %(address)s);
                        """,
                        {
                            "cust_no": cust_no,
                            "name": name,
                            "email": email,
                            "phone": phone or None,
                            "address": address or None,
                        },
                    )

                    conn.commit()
                return redirect(url_for("list_customers"))

    return render_template("add_customer.html")


@app.route("/customers/<cust_no>/delete_customer", methods=("POST",))
def delete_customer(cust_no):
    """Anonymize customer attributes instead of deleting them."""
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("SELECT MAX(email) FROM customer WHERE email LIKE 'X%'")
            max_masked_email = cur.fetchone()[0]

            if max_masked_email is None:
                masked_email = "X000001"
            else:
                # Increment the masked email by 1
                masked_email_number = int(max_masked_email[1:]) + 1
                masked_email = f"X{masked_email_number:06}"

            cur.execute("SELECT MAX(name) FROM customer WHERE name LIKE 'NAME%'")
            max_masked_name = cur.fetchone()[0]

            if max_masked_name is None:
                masked_name = "NAME0000000001"
            else:
                # Increment the masked name by 1
                masked_name_number = int(max_masked_name[4:]) + 1
                masked_name = f"NAME{masked_name_number:010}"

            cur.execute(
                """
                UPDATE customer
                SET name = %(masked_name)s,
                    email = %(masked_email)s,
                    phone = NULL,
                    address = NULL
                WHERE cust_no = %(cust_no)s;
                """,
                {
                    "cust_no": cust_no,
                    "masked_name": masked_name,
                    "masked_email": masked_email,
                },
            )
        conn.commit()
    return redirect(url_for("list_customers"))


#                    d) Realizar encomendas


@app.route("/choose-products/<cust_no>", methods=("GET", "POST"))
def choose_products(cust_no):
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

    return render_template(
        "list.html",
        type="product",
        list=products,
        purpose="make_order",
        cust_no=cust_no,
    )


@app.route("/insertfororder", methods=["GET", "POST"])
def get_cust_no_for_order():
    return render_template("insert.html", type="order", purpose="new_order")


@app.route("/cust_no", methods=["POST"])
def read_cust_no():
    cust_no = int(request.form.get("cust_no_form"))
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                SELECT cust_no 
                FROM customer
                WHERE email NOT LIKE 'X%'
                AND name NOT LIKE 'NAME%'
                """
            )
            lst = [row.cust_no for row in cur.fetchall()]

    if cust_no in lst:
        return redirect(url_for("choose_products", cust_no=cust_no))
    else:
        flash("Cliente não existe na base de dados")
        return render_template("insert.html", type="order", purpose="new_order")


@app.route("/new_order/<cust_no>", methods=("GET", "POST"))
def new_order(cust_no):
    lst = []
    for key, value in request.form.items():
        if key.startswith("product_price_"):
            sku = key.split("_")[2]  # Extract the SKU from the input field name
            quantity = value
            if quantity.isdigit() and int(quantity) != 0:
                lst.append((sku, int(quantity)))

    error = None

    if lst == []:
        error = "Tem de selecionar pelo menos um produto"

    if error is not None:
        flash(error)

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute("SELECT MAX(order_no) FROM orders")
            order_no = cur.fetchone()[0]

            if order_no is None:
                order_no = 1
            else:
                # increment order_no for new order
                order_no += 1

            date = datetime.date.today()
            cur.execute(
                """
                INSERT INTO orders (order_no, cust_no, date)
                VALUES (%(order_no)s, %(cust_no)s, %(date)s);
                """,
                {"order_no": order_no, "cust_no": cust_no, "date": date},
            )

            for product in lst:
                # add products of order to table contains
                sku = product[0]
                qty = product[1]

                cur.execute(
                    """
                    INSERT INTO contains (order_no, sku, qty)
                    VALUES (%(order_no)s, %(sku)s, %(qty)s);
                    """,
                    {"order_no": order_no, "sku": sku, "qty": qty},
                )

            conn.commit()

    return redirect(url_for("homepage"))


#                     e) Simular o pagamento de encomendas


@app.route("/delivery", methods=("GET",))
def list_unpaid_orders():
    """Show unpaid orders"""

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

    return render_template("list.html", type="order", list=unpaid)


@app.route("/insert", methods=("GET", "POST"))
def select_cust_no():
    return render_template("insert.html", type="order", purpose="show_orders")


@app.route("/delivery/show", methods=("POST",))
def show_customer_orders():

    cust_no = int(request.form.get("cust_no_form"))
    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            cur.execute(
                """
                SELECT cust_no 
                FROM customer
                WHERE email NOT LIKE 'X%'
                AND name NOT LIKE 'NAME%'
                """
            )
            lst = [row.cust_no for row in cur.fetchall()]

    if cust_no not in lst:
        flash("Cliente não existe na base de dados")
        return render_template("insert.html", type="order", purpose="show_orders")

    with pool.connection() as conn:
        with conn.cursor(row_factory=namedtuple_row) as cur:
            orders = cur.execute(
                """
                SELECT order_no, cust_no, SUM(qty*price), SUM(qty) as qty_
                FROM orders
                    JOIN contains USING(order_no)
                    JOIN product USING(SKU)
                WHERE cust_no = %(cust_no)s
                AND order_no not in 
                (select order_no from pay)
                GROUP BY order_no
                ORDER BY order_no;
                """,
                {"cust_no": cust_no},
            ).fetchall()
            log.debug(f"Found {cur.rowcount} rows.")

    return render_template("list.html", type="order", list=orders)


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
                    {"order_no": order[0], "cust_no": order[1]},
                )
                conn.commit()

    return render_template("pay.html", order=order)
