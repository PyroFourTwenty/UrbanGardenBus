from flask_wtf import FlaskForm

from wtforms import StringField, PasswordField, FloatField, SubmitField, SelectField, IntegerField, BooleanField
from wtforms.validators import InputRequired,Length,ValidationError,NumberRange
from wtforms.widgets import TextArea
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
            raise ValidationError(
                "That username is taken"
            )

class CreateNewStation(FlaskForm):
    station_name = StringField(validators=[InputRequired()], render_kw={"placeholder":"The new name of the station"})
    latitude = FloatField('Latitude')
    longitude = FloatField('Longitude')
    height = FloatField('Height')

    submit = SubmitField("Save station meta data")

class AddNewSensorToStation(FlaskForm):
    sensor_type = SelectField('Select your sensor model', choices=None)
    sensor_slot = IntegerField('What slot should this sensor register on? (0 to 255)', validators=[InputRequired(),NumberRange(min=0, max=255, message='Something')])
    submit = SubmitField('Add sensor', id='add-sensor-submit')

    def __init__(self, *args, **kwargs):
        super(AddNewSensorToStation,self).__init__(*args, **kwargs)

class AddNewActorToStation(FlaskForm):
    actor_name = StringField(validators=[InputRequired()], render_kw={"placeholder":"The name of the actor"})
    actor_slot = IntegerField('What slot should this actor register on? (0 to 255)', validators=[InputRequired(),NumberRange(min=0, max=255, message='Something')])
    submit = SubmitField('Add actor', id='add-actor-submit')

class CreateNewSensorModelForm(FlaskForm):
    model_name = StringField(validators=[InputRequired(),Length(max=256)], render_kw={"placeholder":"Name of the sensor model"})
    phenomenon_name = StringField(validators=[InputRequired(),Length(max=256)], render_kw={"placeholder":"Name of the observed phenomenon (ie. 'temperature'or 'soil humidity')"})
    unit_name = StringField(validators=[InputRequired(),Length(max=256)], render_kw={"placeholder":"Unit of the measurement (ie. '°C')"})
    calibration_needed = BooleanField(render_kw={"placeholder": "Calibration required for this sensor?"})
    submit = SubmitField("Save sensor model")

class CreateNewPostForm(FlaskForm):
    post_header = StringField(validators=[Length(max=128)], render_kw={"placeholder":"Interesting title (optional)"}) 
    post_text = StringField(validators=[InputRequired(),Length(max=1024)], render_kw={"placeholder":"What do you want to say?"}, widget=TextArea()) 
    submit = SubmitField("Post")

class CreateNewCommentForm(FlaskForm):
    comment_text = StringField(validators=[InputRequired(),Length(max=512)], render_kw={"placeholder":"What are your thoughts?"})
    submit = SubmitField("Comment")
