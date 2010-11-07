from google.appengine.ext import db
from models import base
from hashlib import sha256
import random
import string
class Transcription(base.CommonModel):
	Sid = db.StringProperty()

	
	@classmethod
	def new(cls, key_name, email, password):
		Sid = 'TR'+sha256(email).hexdigest()
		return cls(Sid=Sid)
