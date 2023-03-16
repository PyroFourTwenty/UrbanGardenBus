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
    ttn_enddevice_dev_eui = db.Column(db.String(16),nullable=False)
    ttn_enddevice_dev_id = db.Column(db.String(300),nullable=False)
    ttn_enddevice_app_key = db.Column(db.String(32),nullable=False)
    ttn_enddevice_join_eui= db.Column(db.String(16),nullable=False)
    osem_sensebox_id = db.Column(db.String(24), nullable=False)
    

class Sensor(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    belongs_to_station_id = db.Column(db.Integer, nullable=False)
    sensor_model_id = db.Column(db.Integer, nullable=False)
    station_slot = db.Column(db.Integer, nullable=False)
    osem_sensor_id = db.Column(db.String(24), nullable=False)

class CalibrationValueForSensor(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    belongs_to_sensor_id = db.Column(db.Integer, nullable=False)
    calibration_value = db.Column(db.Float, default = 0.0, nullable=False)

class SensorModel(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    model_name = db.Column(db.String(256), nullable=False)
    phenomenon_name = db.Column(db.String(256), nullable=False)
    unit_name = db.Column(db.String(256), nullable=False)
    calibration_needed = db.Column(db.Boolean, nullable=False)

class Actor(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(256), nullable=False)
    belongs_to_station_id = db.Column(db.Integer, nullable=False)
    station_slot = db.Column(db.Integer, nullable=False)
    actor_value = db.Column(db.Float, default = 0.0, nullable=False)
