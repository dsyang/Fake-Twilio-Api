from google.appengine.ext import db

from models import base, phone_numbers

from random import random

from hashlib import sha256

from helpers import parameters

class Incoming_Phone_Number(phone_numbers.Phone_Number):
	pass