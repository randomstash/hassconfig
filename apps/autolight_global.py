#
# persist_counters App

import appdaemon.plugins.hass.hassapi as hass
import os
import datetime
import pickle
import sqlite3
from contextlib import closing

_counter_filename_ = '/home/homeassistant/.homeassistant/apps/counters.pkl'
_db_filename_ = '/home/homeassistant/.homeassistant/apps/autolight.db'

class AutoLight_Global(hass.Hass):
	counter_dict = {}
	decision_log = []
	autolight_bd = None

	def initialize(self):
		self.log("Hello from AutoLight_Global")

		# Register hourly callback to save everything
		self.daily_handle = self.run_hourly(self.hourly_save, start=datetime.time(0, 0, 0))

		# Register callback to save counters on hass stop
		handle = self.listen_event(self.hass_stopped, event='plugin_stopped')

		# Register callback to load counters on hass start
		# handle = self.listen_event(self.hass_started, event='plugin_started')

		# Register callback on app terminate
		handle = self.listen_event(self.hourly_save, event='terminate')

		# Restore counters
		self.load_counters()

		# Check if DB exists
		if not os.path.isfile(_db_filename_):
			self.log("AutoLight_Global creating new DB")
			tmpconn = sqlite3.connect(_db_filename_)
			with closing(tmpconn.cursor()) as c:
				# ['fake', 4, 10, 'off,off,on,off,off,off,off,on,off,off,off,off,+25.5,33.0', 15, 0]
				c.execute('''CREATE TABLE decisions(
							entity text,
							weekday integer,
							hour integer,
							context text,
							turned_on_interval integer,
							result integer)''')

		# Test
		# self.log("***Saving test fake data")
		# self.book_decision_data('fake1')
		# self.book_decision_result(15, 0)
		# self.save_decision_data()

	def hourly_save(self, event_name, data, kwargs):
		self.log("****saving")
		self.save_counters('dummy arg')
		self.save_decision_data()

	def hass_stopped(self, event_name, data, kwargs):
		self.save_counters('dummy arg')

	# def hass_started(self, event_name, data, kwargs):
	# 	self.load_counters()

	def load_counters(self):
		self.log("Loading persistent counters")
		if os.path.isfile(_counter_filename_):
			self.counter_dict = pickle.load(open(_counter_filename_, 'rb'))
			# Set data
			for counter_name in self.counter_dict.keys():
				self.log("Restoring counter: %s: %s" % (counter_name, self.counter_dict[counter_name]))
				self.set_state(counter_name, state=str(self.counter_dict[counter_name]))
				self.log("done")

	def save_counters(self, kwargs):
		self.log("Saving persistent counters")
		# Save data
		pickle.dump(self.counter_dict, open(_counter_filename_, 'wb'))

	def increment_counter(self, counter_name):
		self.log("AutoLight_Global incrementing counter %s" % counter_name)
		# Increment counter from current state
		self.call_service("counter/increment", entity_id=counter_name)
		# Save in counter_dict
		self.counter_dict[counter_name] = self.get_state(counter_name)


	def book_decision_result(self, variables_data, turned_on_interval, result):
		self.log("book_decision_result: %s / %d / %d" % (variables_data, turned_on_interval, result))
		variables_data.append(turned_on_interval)
		variables_data.append(result)
		self.decision_log.append(variables_data.copy())

		self.log("book_decision_result done 1: %s" % self.decision_log)
		# Clear variables_data
		del variables_data[:]
		self.log("book_decision_result done 2: %s" % self.decision_log)

	def save_decision_data(self):
		if len(self.decision_log) > 0:
			self.log("Saving decision data: %s" % self.decision_log)
			self.log("DB: %s" % _db_filename_)
			con = sqlite3.connect(_db_filename_)
			# Save data
			with con:
				cur = con.cursor()
				cur.executemany("""INSERT INTO decisions VALUES(?,?,?,?,?,?)""", self.decision_log)
				# for d in self.decision_log:
					# self.log("Saving data: %s" % d)
					# ['fake', 4, 10, 'off,off,on,off,off,off,off,on,off,off,off,off,+25.5,33.0', 15, 0]
				# cur.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?)" % (d[0],d[1],d[2],d[3],d[4],d[5]))
			# pickle.dump(self.decision_log, open(filename, 'wb'))
			print("%s" % self.decision_log)
			# Clear data
			self.decision_log = []
		else:
			self.log("No decision data to save")
