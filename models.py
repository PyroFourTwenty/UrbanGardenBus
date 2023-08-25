from flask_login import UserMixin
from database import db
from datetime import datetime
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

class SetActorValue(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    belongs_to_station_id = db.Column(db.Integer, nullable=False)
    station_slot = db.Column(db.Integer, nullable=False)
    actor_value = db.Column(db.Float, default = 0.0, nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    author_id = db.Column(db.Integer, nullable=False)
    header = db.Column(db.String(128), nullable=True)
    text = db.Column(db.String(1024), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    author_id = db.Column(db.Integer, nullable=False)
    belongs_to_post_id = db.Column(db.Integer, nullable=False)
    text = db.Column(db.String(512), nullable=False)

class PostReaction(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    belongs_to_user_id = db.Column(db.Integer, nullable=False)
    belongs_to_post_id = db.Column(db.Integer, nullable=False)
    reaction_type = db.Column(db.String(32), nullable=False)