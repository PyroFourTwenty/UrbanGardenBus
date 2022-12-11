from flask_wtf import FlaskForm

from wtforms import StringField, PasswordField, FloatField, SubmitField, SelectField, IntegerField
from wtforms.validators import InputRequired,Length,ValidationError,NumberRange
from GardenBusClient.SupportedSensors import supported_sensors
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

    submit = SubmitField("Save station meta data")

class AddNewSensorToStation(FlaskForm):
    sensor_type = SelectField('Select your sensor model', choices=None)
    slot = IntegerField('What slot should this sensor register on? (0 to 255)', validators=[InputRequired(),NumberRange(min=0, max=255, message='Something')])
    submit = SubmitField('Add sensor', id='add-sensor-submit')

    def __init__(self, *args, **kwargs):
        super(AddNewSensorToStation,self).__init__(*args, **kwargs)
        sensors_from_file = []
        for sensor in supported_sensors.sensors:
            sensors_from_file.append((sensor,supported_sensors.sensors[sensor]["model_name"]))
        self.sensor_type.choices = sensors_from_file