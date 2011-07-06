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
from gnuradio.wxgui import common, forms
from gnuradio import gr, blks2
from gnuradio.wxgui.pubsub import pubsub
from gnuradio.wxgui.constants import *
import numpy, wx

NEG_INF = float('-inf')
DEFAULT_NUMBER_RATE = gr.prefs().get_long('wxgui', 'number_rate', 5)
DEFAULT_WIN_SIZE = (300, 300)
DEFAULT_GAUGE_RANGE = 1000
VALUE_REPR_KEY = 'value_repr'
VALUE_REAL_KEY = 'value_real'

##################################################
# Number sink block (wrapper for old wxgui)
##################################################
class _number_sink_base(gr.hier_block2):
	"""
	An decimator block with a number window display
	"""

	def __init__(
		self,
		parent,
		unit='%',
		minval=0,
		maxval=100,
		decimal_places=5,
		sample_rate=1,
		number_rate=DEFAULT_NUMBER_RATE,
		label='Bit Error Rate',
		size=DEFAULT_WIN_SIZE,
		show_gauge=True,
		**kwargs #catchall for backwards compatibility
	):
		gr.hier_block2.__init__(
			self,
			"number_sink",
			gr.io_signature(1, 1, self._item_size),
			gr.io_signature(0, 0, 0),
		)
		#blocks
		sd = blks2.stream_to_vector_decimator(
			item_size=self._item_size,
			sample_rate=sample_rate,
			vec_rate=number_rate,
			vec_len=1,
		)
		mult = gr.multiply_const_ff(100)
		add = gr.add_const_ff(1e-10)
		msgq = gr.msg_queue(2)
		sink = gr.message_sink(self._item_size, msgq, True)
		#connect
		self.connect(self, sd, mult, add, sink)
		#controller
		self.controller = pubsub()
		#start input watcher
		common.input_watcher(msgq, self.controller, MSG_KEY)
		#create window
		self.win = number_window(
			parent=parent,
			controller=self.controller,
			size=size,
			title=label,
			units=unit,
			real=self._real,
			minval=minval,
			maxval=maxval,
			decimal_places=decimal_places,
			show_gauge=show_gauge,
			msg_key=MSG_KEY,
			sample_rate_key=SAMPLE_RATE_KEY)

class number_sink_f(_number_sink_base):
	_item_size = gr.sizeof_float
	_real = True


class number_window(wx.Panel, pubsub):
	def __init__(
		self,
		parent,
		controller,
		size,
		title,
		units,
		show_gauge,
		real,
		minval,
		maxval,
		decimal_places,
		msg_key,
		sample_rate_key,
	):
		pubsub.__init__(self)
		wx.Panel.__init__(self, parent, style=wx.SUNKEN_BORDER)
		#setup
		self.peak_val_real = NEG_INF
		self.real = real
		self.units = units
		self.decimal_places = decimal_places
		#proxy the keys
		self.proxy(MSG_KEY, controller, msg_key)
		#initialize values
		self[RUNNING_KEY] = True
		self[VALUE_REAL_KEY] = minval
		#setup the box with display and controls
		main_box = wx.BoxSizer(wx.HORIZONTAL)
		sizer = forms.static_box_sizer(
			parent=self, sizer=main_box, label=title,
			bold=True, orient=wx.VERTICAL, proportion=1,
		)
		sizer.AddStretchSpacer()
		forms.static_text(
			parent=self, sizer=sizer,
			ps=self, key=VALUE_REPR_KEY, width=size[0],
			converter=forms.str_converter(),
		)
		sizer.AddStretchSpacer()
		self.gauge_real = forms.gauge(
			parent=self, sizer=sizer, style=wx.GA_HORIZONTAL,
			ps=self, key=VALUE_REAL_KEY, length=size[0],
			minimum=minval, maximum=maxval, num_steps=DEFAULT_GAUGE_RANGE,
		)
		#hide/show gauges
		self.gauge_real.ShowItems(show_gauge)
		self.SetSizerAndFit(main_box)
		#register events
		self.subscribe(MSG_KEY, self.handle_msg)

	def handle_msg(self, msg):
		if not self[RUNNING_KEY]: return
		format_string = "%%.%df"%self.decimal_places
		sample = numpy.fromstring(msg, numpy.float32)[-1]
		label_text = "%s %s"%(format_string%sample, self.units)
		self[VALUE_REAL_KEY] = sample
		#set label text
		self[VALUE_REPR_KEY] = label_text
		#clear peak hold
