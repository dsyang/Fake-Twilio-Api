#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#	  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

import os
import urllib, urllib2, base64, hmac
import logging

from libraries.gaesessions import get_current_session

from models import accounts, phone_numbers, calls, messages

from helpers import application, authorization, request, twiml

from decorators import webapp_decorator

class MainHandler(webapp.RequestHandler):
	def get(self):
		path = os.path.join(os.path.dirname(__file__), '../templates/home.html')
		self.response.out.write(template.render(path,{}))

class Register(webapp.RequestHandler):
	def get(self):
		path = os.path.join(os.path.dirname(__file__), '../templates/register.html')
		self.response.out.write(template.render(path,{}))

	def post(self):
		from hashlib import sha256
		required = ['email','password','password_confirm']
		if application.required(required,self.request) and self.request.get('password') == self.request.get('password_confirm'):
			exist_account = accounts.Account.get_by_key_name(self.request.get('email'))
			if exist_account is None:
				account = accounts.Account.new(key_name = self.request.get('email').lower(), email=self.request.get('email').lower(),password=self.request.get('password'))
				account.put()
				session = get_current_session()
				session.regenerate_id()
				session['Account'] = account
				self.redirect('/account')
			else:
				Register.get(self)
		else:
			Register.get(self)
		

class Login(webapp.RequestHandler):
	def get(self):
		path = os.path.join(os.path.dirname(__file__), '../templates/login.html')
		self.response.out.write(template.render(path,{}))

	def post(self):
		required = ['email','password']
		if application.required(required,self.request):
			Account = accounts.Account.get_by_key_name(self.request.get('email'))
			if Account is not None and Account.check_password(self.request.get('password')):
				session = get_current_session()
				session.regenerate_id()
				session['Account'] = Account
				self.redirect('/account')
			else:
				Login.get(self)

class Account(webapp.RequestHandler):
	@webapp_decorator.check_logged_in
	def get(self):
		path = os.path.join(os.path.dirname(__file__), '../templates/account.html')
		self.response.out.write(template.render(path,{'data':self.data}))

class PhoneNumbers(webapp.RequestHandler):
	@webapp_decorator.check_logged_in
	def get(self):
		self.data['PhoneNumbers'] = phone_numbers.Phone_Number.all().filter('AccountSid =',self.data['Account'].Sid)
		path = os.path.join(os.path.dirname(__file__), '../templates/phone-numbers.html')
		self.response.out.write(template.render(path,{'data':self.data}))

class PhoneNumber(webapp.RequestHandler):
	@webapp_decorator.check_logged_in
	def get(self,Sid):
		Sid = urllib.unquote(Sid)
		self.data['PhoneNumber'] = phone_numbers.Phone_Number.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Sid = ',Sid).get()
		if self.data['PhoneNumber'] is not None:
			path = os.path.join(os.path.dirname(__file__), '../templates/phone-number.html')
			self.response.out.write(template.render(path,{'data':self.data}))
		else:
			self.redirect('/phone-numbers')

	@webapp_decorator.check_logged_in
	def post(self,Sid):
		from handlers import incoming_phone_numbers

		Sid = urllib.unquote(Sid)

		self.data['PhoneNumber'] = phone_numbers.Phone_Number.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Sid = ',Sid).get()

		if self.data['PhoneNumber'] is not None:
			#authstring = base64.encodestring(self.data['Account'].Sid+':'+self.data['Account'].AuthToken).replace('\n','')
			#self.request.headers['Authorization'] =  'Basic '+str(authstring)
			#print incoming_phone_numbers.IncomingPhoneNumberInstance.post(incoming_phone_numbers.IncomingPhoneNumberInstance(),'2010-04-01',self.data['Account'].Sid, Sid+'.json', request = self.request,response = self.response)
			Valid = True
			for arg in self.request.arguments():
				if Valid:
					Valid,TwilioCode,TwilioMsg =  self.data['PhoneNumber'].validate(self.request, arg, self.request.get( arg ,None))
				setattr(self.data['PhoneNumber'], arg, self.data['PhoneNumber'].sanitize( self.request, arg, self.request.get( arg ,None)))
					
			if Valid:
				self.data['PhoneNumber'].put()
			else:
				self.data['Error'] = True
				self.data['TwilioCode'] = TwilioCode
				self.data['TwilioMsg'] = TwilioMsg
			path = os.path.join(os.path.dirname(__file__), '../templates/phone-number.html')
			self.response.out.write(template.render(path,{'data':self.data}))
		else:
			self.redirect('/phone-numbers')
		
class FakeSms(webapp.RequestHandler):
	@webapp_decorator.check_logged_in
	def get(self,Sid):
		Sid = urllib.unquote(Sid)
		self.data['PhoneNumber'] = phone_numbers.Phone_Number.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Sid = ',Sid).get()
		if self.data['PhoneNumber'] is not None:
			path = os.path.join(os.path.dirname(__file__), '../templates/fake-sms.html')
			self.response.out.write(template.render(path,{'data':self.data}))
		else:
			self.redirect('/phone-numbers')

	@webapp_decorator.check_logged_in
	def post(self,Sid):
		self.data['PhoneNumber'] = phone_numbers.Phone_Number.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Sid = ',Sid).get()
		if self.data['PhoneNumber'] is not None:
			#########Doing webapp error checking!
			REQUIRED = ['From','Body']
			ALLOWED_PARAMETERS = ['FromCity','FromState','FromZip','FromCounty','ToCity','ToState','ToZip','ToCounty']
			Valid = True
			Any = False
			Blank = False
			for param in REQUIRED:
				if self.request.get(param,'') == '':
					Valid = False
			for param in ALLOWED_PARAMETERS:
				if self.request.get(param,'') != '':
					Any = True
				else:
					Blank = True
			if Valid and (Any and Blank):
				Valid = False
			if Valid:
			### ERROR CHECKING DONE FOR PASSED IN
				logging.info(self.data['PhoneNumber'].PhoneNumber)
				Message, Valid, self.data['TwilioCode'],self.data['TwilioMsg'] = messages.Message.new(
											To = self.data['PhoneNumber'].PhoneNumber,
											From = self.request.get('From'),
											Body = self.request.get('Body'),
											request = self.request,
											AccountSid = self.data['Account'].Sid,
											Direction = 'incoming',
											Status = 'sent'
										)
				#CHECK IF WE'VE PASSED VALID INFO TO MESSAGE
				if Valid:
					Message.put()
					Payload = Message.get_dict()
					#This is some really really bad bad form processing
					Payload = {}
					for param in ALLOWED_PARAMETERS:
						Payload[param] = self.request.get(param)
					#has to have a smsurl, not necessarily fallback url
					GoodResponse = False
					self.data['Response'] = request.request_twiml(self.data['Account'], self.data['PhoneNumber'].SmsUrl, self.data['PhoneNumber'].SmsMethod, Payload)
					if 400 <= self.data['Response'].status_code <= 600:
						#bad response and see if there is a fallback and repeat	
						if self.data['PhoneNumber'].SmsFallbackUrl is not None and self.data['PhoneNumber'].SmsFallbackUrl != '':
							self.data['FallbackResponse'] = request.request_twiml(self.data['Account'], self.data['PhoneNumber'].SmsFallbackUrl, self.data['PhoneNumber'].SmsFallbackMethod, Payload)
							if 200 <= self.data['FallbackResponse'].status_code <=300:
								twiml_object  = twiml.parse_twiml(self.data['FallbackResponse'].content)
					elif 200<= self.data['Response'].status_code <= 300:
						twiml_object  = twiml.parse_twiml(self.data['Response'].content)
					
						#parse the twiml and do some fake things
					path = os.path.join(os.path.dirname(__file__), '../templates/fake-sms-result.html')
					self.response.out.write(template.render(path,{'data':self.data}))
				else:
					self.data['Arguments'] = {}
					for key in self.request.arguments():
						self.data['Arguments'][key] = self.request.get(key,'')
					FakeSms.get(self,Sid)
			else:
				self.data['Arguments'] = {}
				for key in self.request.argument():
					self.data['Arguments'][key] = self.request.get(key,'')
				FakeSms.get(self,Sid)
		else:
			self.redirect('/phone-numbers')
class FakeVoice(webapp.RequestHandler):
	"""
	Parameter	Description
	CallSid	A unique identifier for this call, generated by Twilio.
	AccountSid	Your Twilio account id. It is 34 characters long, and always starts with the letters AC.
	From	The phone number of the party that initiated the call. Formatted with a '+' and country code e.g., +16175551212 (E.164 format). If the call is inbound, then it is the caller's caller ID. If the call is outbound, i.e., initiated via a request to the REST API, then this is the phone number you specify as the caller ID.
	To	The phone number of the called party. Formatted with a '+' and country code e.g., +16175551212 (E.164 format). If the call is inbound, then it's your Twilio phone number. If the call is outbound, then it's the phone number you provided to call.
	CallStatus	A descriptive status for the call. The value is one of queued, ringing, in-progress, completed, busy, failed or no-answer. See the CallStatus section below for more details.
	ApiVersion	The version of the Twilio API used to handle this call. For incoming calls, this is determined by the API version set on the called number. For outgoing calls, this is the API version used by the outgoing call's REST API request.
	Direction	Indicates the direction of the call. In most cases this will be inbound, but if you are using <Dial> it will be outbound-dial.
	ForwardedFrom	This parameter is set only when Twilio receives a forwarded call, but its value depends on the caller's carrier including information when forwarding. Not all carriers support passing this information.
	"""
	
	@webapp_decorator.check_logged_in
	def get(self,Sid):
		Sid = urllib.unquote(Sid)
		self.data['PhoneNumber'] = phone_numbers.Phone_Number.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Sid = ',Sid).get()
		if self.data['PhoneNumber'] is not None:
			path = os.path.join(os.path.dirname(__file__), '../templates/fake-voice.html')
			self.response.out.write(template.render(path,{'data':self.data}))
		else:
			self.redirect('/phone-numbers')

	@webapp_decorator.check_logged_in
	def post(self,Sid):
		ALLOWED_PARAMETERS = ['From','FromCity','FromState','FromZip','FromCounty','ToCity','ToState','ToZip','ToCounty']
		#Create a fake call
		
		
class Calls(webapp.RequestHandler):
	@webapp_decorator.check_logged_in
	def get(self):
		self.data['QueuedCalls'] = calls.Calls.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Status = ','queued').get()
		self.data['RingingCalls'] = calls.Calls.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Status = ','ringing').get()
		self.data['InProgressCalls'] = calls.Calls.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Status = ','in-progress').get()
		self.data['CompletedCalls'] = calls.Calls.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Status = ','completed').get()
		self.data['BusyCalls'] = calls.Calls.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Status = ','busy').get()
		self.data['NoAnswerCalls'] = calls.Calls.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Status = ','no-answer').get()
		self.data['CanceledCalls'] = calls.Calls.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Status = ','canceled').get()
		path = os.path.join(os.path.dirname(__file__), '../templates/calls.html')
		self.response.out.write(template.render(path,{'data':self.data}))
		

class Call(webapp.RequestHandler):
	@webapp_decorator.check_logged_in
	def get(self,Sid):
		Sid = urllib.unquote(Sid)
		self.data['Call'] = calls.Call.all().filter('AccountSid = ',self.data['Account'].Sid).filter('Sid = ',Sid).get()
		if self.data['Call'] is not None:
			path = os.path.join(os.path.dirname(__file__), '../templates/call.html')
			self.response.out.write(template.render(path,{'data':self.data}))
		else:
			self.redirect('/calls')

class Logout(webapp.RequestHandler):
	def get(self):
		session = get_current_session()
		session.terminate()
		self.redirect('/')
def main():
	application = webapp.WSGIApplication([
											('/', MainHandler),
											('/register',Register),
											('/login',Login),
											('/logout',Logout),
											('/account',Account),
											('/calls', Calls),
											('/calls/(.*)',Call),
											('/phone-numbers',PhoneNumbers),
											('/phone-numbers/sms/(.*)',FakeSms),
											('/phone-numbers/voice/(.*)',FakeVoice),
											('/phone-numbers/(.*)',PhoneNumber)
										],
										 debug=True)
	util.run_wsgi_app(application)


if __name__ == '__main__':
	main()
