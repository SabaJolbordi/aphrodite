from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

import cloudinary
import cloudinary.uploader

# დაამატეთ კონფიგურაცია
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)





# Initialize Flask app and set up the database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///products.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'
db = SQLAlchemy(app)

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'




# Define the Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String, nullable=True)  # Main image URL
    additional_images = db.Column(db.Text, nullable=True)  # Comma-separated URLs for additional images
    category = db.Column(db.String(50), nullable=False)  # New category field


# Define the User model for registration and login
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')  # Add a role field


# Define the Order model for tracking product purchases
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Add created_at field

    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    product = db.relationship('Product', backref=db.backref('orders', lazy=True))


# Load user function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Create an admin user if it does not exist
def create_admin_user():
    admin_user = User.query.filter_by(username='barbare').first()
    if not admin_user:
        hashed_password = generate_password_hash('aphrodite')
        admin_user = User(username='barbare', password=hashed_password, role='admin', email='admin@example.com')
        db.session.add(admin_user)
        db.session.commit()


# Ensure tables are created and admin user is created
with app.app_context():
    db.create_all()
    create_admin_user()





# Home route to display all products
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)


# Route to view a specific product's details
@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('product_detail.html', product=product)


# Route to handle product purchase (buy button functionality)
@app.route('/buy/<int:product_id>', methods=['POST'])
@login_required
def buy_product(product_id):
    product = Product.query.get_or_404(product_id)

    if not product:  # Ensure product exists
        flash("Product not found.", "danger")
        return redirect(url_for('index'))

    order = Order(user_id=current_user.id, product_id=product.id)

    try:
        db.session.add(order)
        db.session.commit()  # Commit the order to the database
        flash("Product purchased successfully!", "success")
    except Exception as e:
        db.session.rollback()  # In case of an error, rollback the session
        flash(f"An error occurred while processing your purchase: {e}", "danger")

    return redirect(url_for('thank_you'))


# Route for admin to view all orders
@app.route('/orders')
@login_required
def orders():
    if current_user.role == 'admin':
        # Get all orders along with related user and product data
        orders = Order.query.join(User).join(Product).all()
        return render_template('orders.html', orders=orders)
    else:
        return redirect(url_for('index'))


# Route to add a new product (restricted to admin)
def admin_required(f):
    def wrapper(*args, **kwargs):
        if current_user.role != 'admin':  # Check if the user has the 'admin' role
            flash("You do not have permission to access this page", "danger")
            return redirect(url_for('index'))  # Redirect non-admin users to the homepage
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


# Route to add a new product (restricted to admin)
@app.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']  # Get category from the form
        image_url = request.form['image_url'] if request.form['image_url'] else None
        additional_images = request.form.get('additional_images', None)

        new_product = Product(
            title=title,
            description=description,
            price=price,
            category=category,
            image_url=image_url,
            additional_images=additional_images
        )

        try:
            db.session.add(new_product)
            db.session.commit()
            flash("Product added successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while adding the product: {e}", "danger")

        return redirect(url_for('index'))

    return render_template('add_product.html')


# Route to edit an existing product (restricted to admin)
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.title = request.form['title']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.image_url = request.form['image_url']
        product.additional_images = request.form.get('additional_images', product.additional_images)

        try:
            db.session.commit()
            flash("Product updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while updating the product: {e}", "danger")

        return redirect(url_for('index'))

    return render_template('edit_product.html', product=product)


# Route to delete a product (restricted to admin)
@app.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted successfully!", "success")
    return redirect(url_for('index'))


# Route to show About Us page
@app.route('/about')
def about():
    return render_template('about.html')


# Route to show Contact Us page
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        flash("Thank you for your message!", "success")
        return redirect(url_for('index'))

    return render_template('contact.html')


# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Check if the username or email is already taken
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("მომხმარებლის სახელი უკვე გამოყენებულია. გთხოვთ სცადოთ სხვა.", "danger")
            return redirect(url_for('register'))  # Redirect back to registration form

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash("ელფოსტა უკვე რეგისტრირებულია. გთხოვთ გამოიყენოთ სხვა.", "danger")
            return redirect(url_for('register'))  # Redirect back to registration form

        # Create new user if username and email are not taken
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()

        flash("წარმატებით დარეგისტრირდით! გთხოვთ შედით.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Query to check if the user exists
        user = User.query.filter_by(username=username).first()

        if not user:
            flash("იუზერნეიმი ვერ მოიძებნა, სცადეთ თავიდან.", "danger")  # Specific flash message if username doesn't exist
        elif user and check_password_hash(user.password, password):
            login_user(user)  # Login the user
            flash("Logged in successfully!", "success")  # Flash success message
            return redirect(url_for('index'))  # Redirect to the home page (or dashboard)
        else:
            flash("პაროლი არასწორია", "danger")  # Flash error message if the password is incorrect

    return render_template('login.html')


# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for('index'))


@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').strip()
    if query:
        # Search for products by title or description
        products = Product.query.filter(
            (Product.title.ilike(f'%{query}%')) | (Product.description.ilike(f'%{query}%'))
        ).all()
    else:
        products = []

    return render_template('search_results.html', products=products, query=query)


@app.route('/category/<string:category>')
def filter_by_category(category):
    # Fetch products belonging to the specified category
    products = Product.query.filter_by(category=category).all()
    return render_template('category.html', products=products, category=category)


# Route to delete an order (restricted to admin)
@app.route('/delete_order/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    try:
        db.session.delete(order)
        db.session.commit()
        flash("Order deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while deleting the order: {e}", "danger")

    return redirect(url_for('orders'))

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')


# Run the app
if __name__ == '__main__':
    app.run(debug=True)
