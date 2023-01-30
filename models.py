from flask_login import UserMixin
from database import db

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)

class Station(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    station_name = db.Column(db.String(256), nullable=False)
    belongs_to_user_id = db.Column(db.Integer, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    height = db.Column(db.Float)

class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    belongs_to_station_id = db.Column(db.Integer, nullable=False)
    sensor_model_id = db.Column(db.Integer, nullable=False)
    station_slot = db.Column(db.Integer, nullable=False)

class CalibrationValueForSensor(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    belongs_to_sensor_id = db.Column(db.Integer, nullable=False)
    calibration_value = db.Column(db.Float, nullable=False)

class SensorModel(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    model_name = db.Column(db.String(256), nullable=False)
    phenomenon_name = db.Column(db.String(256), nullable=False)
    unit_name = db.Column(db.String(256), nullable=False)
    calibration_needed = db.Column(db.Boolean, nullable=False)