from flask_wtf import FlaskForm

from wtforms import StringField, PasswordField, FloatField, SubmitField
from wtforms.validators import InputRequired,Length,ValidationError
from models import User
class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder":"Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder":"Password"})
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder":"Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder":"Password"})
    submit = SubmitField("Register")

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()
        if existing_user_username:
            print("That user already exists")
            raise ValidationError(
                "That username is taken"
            )

class CreateNewStation(FlaskForm):
    station_name = StringField(validators=[InputRequired()], render_kw={"placeholder":"The new name of the station"})
    latitude = FloatField('Latitude')
    longitude = FloatField('Longitude')
    height = FloatField('Height')