from flask import Flask, render_template, redirect, url_for, flash
from flask_login import login_user, LoginManager, login_required, logout_user, current_user
from forms import LoginForm, RegisterForm, CreateNewStation
from models import User
from database import db
from flask_bcrypt import Bcrypt


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
bcrypt = Bcrypt(app)

app.config['SECRET_KEY'] = 'thisisasecret'

db.init_app(app)
with app.app_context():
    db.create_all()


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('dashboard'))
    return render_template('login.html',form=form)


@app.route('/dashboard',methods=['GET','POST'])
@login_required
def dashboard():
    return render_template('dashboard.html',username=current_user.username)

@app.route('/stations',methods=['GET','POST'])
@login_required
def stations():
    form = CreateNewStation(latitude=52.456463, longitude=13.52339, height=36.0)
#    form.latitude = 52.456463
    return render_template('stations.html',form=form)


@app.route('/register', methods=['GET','POST'])
def register():
    form = RegisterForm()
    print('aayyy')
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        if User.query.filter_by(username=form.username.data).first():
            print("A user with this name already exists")
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html',form=form)


@app.route('/logout', methods=['GET','POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':

    app.run(debug=True)