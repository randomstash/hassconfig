import appdaemon.plugins.hass.hassapi as hass
from datetime import timedelta, datetime
import pickle
import inspect


class AutoLight(hass.Hass):
	light_switch = None
	light_timer = None
	max_backoff = None
	is_dark = False
	min_timeoff_interval = 3
	last_auto_turn_off = datetime.min
	callback_turn_off_handle = None
	variables_data = []

	def initialize(self):
		self.autolight_controller = self.get_app('auto_light_global')
		self.light_switch = self.args["light_switch"]
		self.light_timer = self.args["light_timer"]
		self.max_backoff = self.args["max_backoff"]

		self.log("Hello from AutoLight - %s" % self.light_switch.split(".",1)[1])
		self.log("Switch [%s] state: %s" % (self.light_switch, self.get_state(self.light_switch)))
		self.log("Timer [%s] state: %s" % (self.light_switch, self.get_state(self.light_timer)))

		# If initial state is on, queue callback_turn_off
		if self.get_state(self.light_switch) == 'on':
			self.callback_turn_off_handle = self.run_in(self.callback_turn_off, int(float(self.get_state(self.light_timer))))

		# Register sunrise/sunset callbacks
		self.run_at_sunrise(self.sunrise_cb, offset=10*60)
		self.run_at_sunset(self.before_sunset_cb, offset=-10*60)

		# Register listener for state change
		self.listen_state(self.state_change, self.light_switch)

		# Register callback on app terminate
		handle = self.listen_event(self.terminate, event='terminate')

		self.autolight_controller.increment_counter('counter.auto_turn_off')
		self.autolight_controller.increment_counter('counter.auto_turn_off_wrong')


	def sunrise_cb(self, kwargs):
		self.is_dark = False
		self.set_state(self.light_timer, state="5")

	def before_sunset_cb(self, kwargs):
		self.is_dark = True
		self.set_state(self.light_timer, state="20")

	def terminate(self):
		self.log("****Terminating AutoLight")
		# Log any pending results
		if len(self.variables_data) > 0:
			turned_on_interval = (self.datetime() - self.last_auto_turn_off).seconds - timedelta(seconds=int(float(self.get_state(self.light_timer)))).seconds
			if (turned_on_interval < self.min_timeoff_interval * 60):
				# We made a bad decision
				self.autolight_controller.book_decision_result(self.variables_data, turned_on_interval, False)
			else:
				# We made a good decision
				self.autolight_controller.book_decision_result(self.variables_data, turned_on_interval, True)         

	def state_change(self, entity, attribute, old, new, kwargs):
		turned_on_interval = (self.datetime() - self.last_auto_turn_off).seconds - timedelta(seconds=int(float(self.get_state(self.light_timer)))).seconds
		if old == "off" and new == "on":
			self.log("Switch [%s] change state %s => %s" % (self.light_switch, old, new))
			# self.log("Elapsed time since last turned on: %s seconds" %
			#          (self.datetime() - self.last_auto_turn_off).seconds)
			# self.log("Elapsed time since last turned on - timer: %s seconds" % (
			#         (self.datetime() - self.last_auto_turn_off).seconds - timedelta(seconds=int(float(self.get_state(self.light_timer)))).seconds))

			# Check if we're tracking yet or if it's a new event
			if len(self.variables_data) > 0:
				if (turned_on_interval < self.min_timeoff_interval * 60):
					# We made a bad decision
					self.autolight_controller.book_decision_result(self.variables_data, turned_on_interval, 1)

					# Update counter, wrong decision made
					self.autolight_controller.increment_counter('counter.auto_turn_off_wrong' + '_' + self.light_switch.split(".",1)[1])
					self.autolight_controller.increment_counter('counter.auto_turn_off_wrong')

					# Increase the backoff timer for the switch
					new_backoff = min(int(float(self.get_state(self.light_timer))) * 2, self.max_backoff)
					self.log("Switch [%s] new backoff timer %s" % (self.light_switch, new_backoff))
					self.set_state(self.light_timer, state=str(new_backoff))

					# Notify phone
					self.notify("AutoLight bad decision - %s" % self.light_switch.split(".",1)[1], title = "AutoLight", name = "ios_iphonem")
				else:
					# We made a good decision
					self.autolight_controller.book_decision_result(self.variables_data, turned_on_interval, 2)

			# Register turn off callback
			if self.light_switch.split(".",1)[1] == 'test':
				self.log("Scheduling auto-off for: %s" % int(float(self.get_state(self.light_timer))))
				self.callback_turn_off_handle = self.run_in(self.callback_turn_off, int(float(self.get_state(self.light_timer))))
			else:
				self.log("Scheduling auto-off for: %s" % int(float(self.get_state(self.light_timer))) * 60)
				self.callback_turn_off_handle = self.run_in(self.callback_turn_off, int(float(self.get_state(self.light_timer))) * 60)
		elif old == "on" and new == "off":
			# User turned off light before the timer kicked in
			self.log("Switch [%s] manually changed state %s => %s" % (self.light_switch, old, new))
			# We need to cancel the scheduled callback_turn_off
			if self.callback_turn_off_handle is not None:
				self.cancel_timer(self.callback_turn_off_handle)
			if len(self.variables_data) < 0:
				# Log
				self.autolight_controller.book_decision_result(self.variables_data, turned_on_interval, 3)


	def book_decision_data(self, entity):
		variables = ["switch.luces_jardin_switch", "switch.luces_jardin_switch_2", "switch.persiana_comedor_switch", "switch.luces_bano1_switch_3", "switch.luces_bano1_switch_2", "switch.luces_bano1_switch", "switch.luces_hab2_switch_2", "switch.luces_hab2_switch", "switch.luces_hab2_switch_3", "switch.luces_pasillo_switch_2", "switch.luces_pasillo_switch_3", "switch.luces_pasillo_switch", "sensor.solar_angle","sensor.pir_bano_luminance"]
		self.log("book_decision_data")
		self.variables_data.append(entity)
		self.variables_data.append(self.datetime().weekday())
		self.variables_data.append(self.datetime().hour)
		self.variables_data.append(','.join(list(map(lambda x: self.get_state(x), variables))))
		self.log("book_decision_data done: %s" % self.variables_data)

	def callback_turn_off(self, kwargs):
		if self.get_state(self.light_switch) == 'on':
			self.log("Switch [%s] auto-turnoff" % self.light_switch)

			# Save decision data
			self.book_decision_data(self.light_switch)

			# Turn switch off
			self.call_service("switch/turn_off", entity_id=self.light_switch)

			# Notify phone
			# self.notify("AutoLight turned off - %s" % self.light_switch.split(".",1)[1], title = "AutoLight", name = "ios_iphonem")

			# Update counter
			self.autolight_controller.increment_counter('counter.auto_turn_off' + '_' + self.light_switch.split(".",1)[1])
			self.autolight_controller.increment_counter('counter.auto_turn_off')

			# Record last_auto_turn_off
			self.last_auto_turn_off = self.datetime()


