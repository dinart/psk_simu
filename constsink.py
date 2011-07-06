#!Modified Version, does not have control GUI!
#
# Copyright 2008 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

##################################################
# Imports
##################################################
from gnuradio.wxgui import common, plotter
from gnuradio import gr, blks2
from gnuradio.wxgui.pubsub import pubsub
from gnuradio.wxgui.constants import *
import wx, numpy

##################################################
# Constellation sink block (wrapper for old wxgui)
##################################################
class const_sink_c(gr.hier_block2):
	"""
	A constellation block with a gui window.
	"""

	def __init__(
		self,
		parent,
		title='',
		sample_rate=1,
		size=(495,450),
		frame_rate=5,
		const_size=256,
		#mpsk recv params
		M=4,
		theta=0,
		alpha=0.005,
		fmax=0.06,
		mu=0.5,
		gain_mu=0.005,
		symbol_rate=1,
		omega_limit=0.005,):
		#init
		gr.hier_block2.__init__(
			self,
			"const_sink",
			gr.io_signature(1, 1, gr.sizeof_gr_complex),
			gr.io_signature(0, 0, 0),
		)
		#blocks
		self.alpha = alpha
		self.fmax = fmax
		self.sd = blks2.stream_to_vector_decimator(
			item_size=gr.sizeof_gr_complex,
			sample_rate=sample_rate,
			vec_rate=frame_rate,
			vec_len=const_size,
		)
		self.beta = .25*self.alpha**2 #redundant, will be updated
		self.fmin = -self.fmax
		self.gain_omega = .25*gain_mu**2 #redundant, will be updated
		self.omega = 1 #set_sample_rate will update this
		self.mu = mu
		self.gain_mu=gain_mu
		self.omega_limit=omega_limit
		# Costas frequency/phase recovery loop
		# Critically damped 2nd order PLL
		self.agc = gr.feedforward_agc_cc(16, 1.1)
		self._costas = gr.costas_loop_cc(self.alpha, self.beta, self.fmax, self.fmin, M)
		# Timing recovery loop
		# Critically damped 2nd order DLL
		self._retime = gr.clock_recovery_mm_cc(self.omega, self.gain_omega, self.mu, self.gain_mu, self.omega_limit)
		msgq = gr.msg_queue(2)
		sink = gr.message_sink(gr.sizeof_gr_complex*const_size, msgq, True)
		#connect
		self.connect(self, self.agc, self._costas, self._retime, self.sd, sink)
		
		#controller
		def setter(p, k, x): p[k] = x
		
		self.controller = pubsub()
		self.controller.subscribe(ALPHA_KEY, self._costas.set_alpha)
		self.controller.publish(ALPHA_KEY, self._costas.alpha)
		self.controller.subscribe(BETA_KEY, self._costas.set_beta)
		self.controller.publish(BETA_KEY, self._costas.beta)
		self.controller.subscribe(GAIN_MU_KEY, self._retime.set_gain_mu)
		self.controller.publish(GAIN_MU_KEY, self._retime.gain_mu)
		self.controller.subscribe(OMEGA_KEY, self._retime.set_omega)
		self.controller.publish(OMEGA_KEY, self._retime.omega)
		self.controller.subscribe(GAIN_OMEGA_KEY, self._retime.set_gain_omega)
		self.controller.publish(GAIN_OMEGA_KEY, self._retime.gain_omega)
		self.controller.subscribe(SAMPLE_RATE_KEY, self.sd.set_sample_rate)
		self.controller.subscribe(SAMPLE_RATE_KEY, lambda x: setter(self.controller, OMEGA_KEY, float(x)/symbol_rate))
		self.controller.publish(SAMPLE_RATE_KEY, self.sd.sample_rate)
		#initial update
		self.controller[SAMPLE_RATE_KEY] = sample_rate
		#start input watcher
		common.input_watcher(msgq, self.controller, MSG_KEY)
		#create window
		self.win = const_window(
			parent=parent,
			controller=self.controller,
			size=size,
			title=title,
			msg_key=MSG_KEY,
			alpha_key=ALPHA_KEY,
			beta_key=BETA_KEY,
			gain_mu_key=GAIN_MU_KEY,
			gain_omega_key=GAIN_OMEGA_KEY,
			omega_key=OMEGA_KEY,
			sample_rate_key=SAMPLE_RATE_KEY,
		)
		common.register_access_methods(self, self.win)
		
	def change_M(self,new_M):
		self.disconnect(self.agc,self._costas)
		self.disconnect(self._costas,self._retime,self.sd)
		
		del(self._costas)
		#del(self._retime)
		
		self._costas = gr.costas_loop_cc(self.alpha, self.beta, self.fmax, self.fmin, new_M)
		#self._retime = gr.clock_recovery_mm_cc(self.omega, self.gain_omega, self.mu, self.gain_mu, self.omega_limit)
		
		self.connect(self.agc,self._costas)
		self.connect(self._costas,self._retime,self.sd)
		

##################################################
# Constellation window with plotter and control panel
##################################################
class const_window(wx.Panel, pubsub):
	def __init__(
		self,
		parent,
		controller,
		size,
		title,
		msg_key,
		alpha_key,
		beta_key,
		gain_mu_key,
		gain_omega_key,
		omega_key,
		sample_rate_key,
	):
		pubsub.__init__(self)
		#proxy the keys
		self.proxy(MSG_KEY, controller, msg_key)
		self.proxy(ALPHA_KEY, controller, alpha_key)
		self.proxy(BETA_KEY, controller, beta_key)
		self.proxy(GAIN_MU_KEY, controller, gain_mu_key)
		self.proxy(GAIN_OMEGA_KEY, controller, gain_omega_key)
		self.proxy(OMEGA_KEY, controller, omega_key)
		self.proxy(SAMPLE_RATE_KEY, controller, sample_rate_key)
		#initialize values
		self[RUNNING_KEY] = True
		self[X_DIVS_KEY] = 10
		self[Y_DIVS_KEY] = 10
		self[MARKER_KEY] = 1.5
		#init panel and plot
		wx.Panel.__init__(self, parent, style=wx.SIMPLE_BORDER)
		self.plotter = plotter.channel_plotter(self)
		self.plotter.SetSize(wx.Size(*size))
		self.plotter.set_title(title)
		self.plotter.set_x_label('Inphase')
		self.plotter.set_y_label('Quadrature')
		self.plotter.enable_point_label(True)
		self.plotter.enable_grid_lines(True)

		#alpha and gain mu 2nd orders
		def set_beta(alpha): self[BETA_KEY] = .25*alpha**2
		self.subscribe(ALPHA_KEY, set_beta)
		def set_gain_omega(gain_mu): self[GAIN_OMEGA_KEY] = .25*gain_mu**2
		self.subscribe(GAIN_MU_KEY, set_gain_omega)
		#register events
		self.subscribe(MSG_KEY, self.handle_msg)
		self.subscribe(X_DIVS_KEY, self.update_grid)
		self.subscribe(Y_DIVS_KEY, self.update_grid)
		#initial update
		self.update_grid()

	def handle_msg(self, msg):
		"""
		Plot the samples onto the complex grid.
		@param msg the array of complex samples
		"""
		if not self[RUNNING_KEY]: return
		#convert to complex floating point numbers
		samples = numpy.fromstring(msg, numpy.complex64)
		real = numpy.real(samples)
		imag = numpy.imag(samples)
		#plot
		self.plotter.set_waveform(
			channel=0,
			samples=(real, imag),
			color_spec=(0,0,1),
			marker=1.5,
		)
		#update the plotter
		self.plotter.update()

	def update_grid(self):
		#update the x axis
		x_max = 1.25
		self.plotter.set_x_grid(-x_max, x_max, common.get_clean_num(2.0*x_max/self[X_DIVS_KEY]))
		#update the y axis
		y_max = 1.25
		self.plotter.set_y_grid(-y_max, y_max, common.get_clean_num(2.0*y_max/self[Y_DIVS_KEY]))
		#update plotter
		self.plotter.update()

