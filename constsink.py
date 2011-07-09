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
import utils
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
		const_size=1024,
		mod='DBPSK'):
		#init
		gr.hier_block2.__init__(
			self,
			"const_sink",
			gr.io_signature(1, 1, gr.sizeof_gr_complex),
			gr.io_signature(0, 0, 0),
		)
		self.sd = blks2.stream_to_vector_decimator(
			item_size=gr.sizeof_gr_complex,
			sample_rate=sample_rate,
			vec_rate=frame_rate,
			vec_len=const_size,
		)
		self. agc = gr.agc2_cc(0.6e-1, 1e-3, 1, 1, 100)
		self.gain= gr.multiply_const_cc(utils.gain[mod])
		msgq = gr.msg_queue(2)
		sink = gr.message_sink(gr.sizeof_gr_complex*const_size, msgq, True)
		#connect
		self.connect(self, self.agc, self.gain, self.sd, sink)
		
		#controller
		def setter(p, k, x): p[k] = x
		
		self.controller = pubsub()
		#initial update
		common.input_watcher(msgq, self.controller, MSG_KEY)
		#create window
		self.win = const_window(
			parent=parent,
			controller=self.controller,
			size=size,
			title=title,
			msg_key=MSG_KEY
		)
		common.register_access_methods(self, self.win)
		
	def change_mod(self,mod):
		self.gain.set_k(utils.gain[mod])
		
		

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
		msg_key
	):
		pubsub.__init__(self)
		#proxy the keys
		self.proxy(MSG_KEY, controller, msg_key)
		#initialize values
		self[RUNNING_KEY] = True
		self[X_DIVS_KEY] = 8
		self[Y_DIVS_KEY] = 8
		self[MARKER_KEY] = 2.0
		#init panel and plot
		wx.Panel.__init__(self, parent, style=wx.SIMPLE_BORDER)
		self.plotter = plotter.channel_plotter(self)
		self.plotter.SetSize(wx.Size(*size))
		self.plotter.set_title(title)
		self.plotter.set_x_label('Inphase')
		self.plotter.set_y_label('Quadrature')
		self.plotter.enable_point_label(False)
		self.plotter.enable_grid_lines(True)

		self.subscribe(MSG_KEY, self.handle_msg)
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
			marker=2.0,
		)
		#update the plotter
		self.plotter.update()

	def update_grid(self):
		#update the x axis
		x_max = 1.75
		self.plotter.set_x_grid(-x_max, x_max, common.get_clean_num(2.0*x_max/self[X_DIVS_KEY]))
		#update the y axis
		y_max = 1.75
		self.plotter.set_y_grid(-y_max, y_max, common.get_clean_num(2.0*y_max/self[Y_DIVS_KEY]))
		#update plotter
		self.plotter.update()

