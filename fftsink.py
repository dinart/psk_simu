#!Modified Version, does not have control GUI!
#
# Copyright 2008,2009,2010 Free Software Foundation, Inc.
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

from __future__ import division

##################################################
# Imports
##################################################
import fftwin

from gnuradio.wxgui import common
from gnuradio import gr, blks2
from gnuradio.wxgui.pubsub import pubsub
from gnuradio.wxgui.constants import *
import math

##################################################
# FFT sink block (wrapper for old wxgui)
##################################################
class _fft_sink_base(gr.hier_block2, common.wxgui_hb):
    """
    An fft block with real/complex inputs and a gui window.
    """

    def __init__(
        self,
        parent,
        baseband_freq=0,
        ref_scale=2.0,
        y_per_div=20,
        y_divs=5,
        ref_level=0,
        sample_rate=1,
        fft_size=128,
        fft_rate=4,
        average=True,
        avg_alpha=0.4,
        title='Baseband Frequency Domain',
        size=fftwin.DEFAULT_WIN_SIZE,
        peak_hold=False,
        win=None,
                use_persistence=False,
                persist_alpha=None,
        **kwargs #do not end with a comma
    ):
        #ensure avg alpha
        if avg_alpha is None: avg_alpha = 2.0/fft_rate
                #ensure analog alpha
        if persist_alpha is None: 
                  actual_fft_rate=float(sample_rate/fft_size)/float(max(1,int(float((sample_rate/fft_size)/fft_rate))))
                  #print "requested_fft_rate ",fft_rate
                  #print "actual_fft_rate    ",actual_fft_rate
                  analog_cutoff_freq=0.5 # Hertz
                  #calculate alpha from wanted cutoff freq
                  persist_alpha = 1.0 - math.exp(-2.0*math.pi*analog_cutoff_freq/actual_fft_rate)
                  
        #init
        gr.hier_block2.__init__(
            self,
            "fft_sink",
            gr.io_signature(1, 1, self._item_size),
            gr.io_signature(0, 0, 0),
        )
        #blocks
        fft = self._fft_chain(
            sample_rate=sample_rate,
            fft_size=fft_size,
            frame_rate=fft_rate,
            ref_scale=ref_scale,
            avg_alpha=avg_alpha,
            average=average,
            win=win,
        )
        msgq = gr.msg_queue(2)
        sink = gr.message_sink(gr.sizeof_float*fft_size, msgq, True)


        #controller
        self.controller = pubsub()
        self.controller.subscribe(AVERAGE_KEY, fft.set_average)
        self.controller.publish(AVERAGE_KEY, fft.average)
        self.controller.subscribe(AVG_ALPHA_KEY, fft.set_avg_alpha)
        self.controller.publish(AVG_ALPHA_KEY, fft.avg_alpha)
        self.controller.subscribe(SAMPLE_RATE_KEY, fft.set_sample_rate)
        self.controller.publish(SAMPLE_RATE_KEY, fft.sample_rate)
        #start input watcher
        common.input_watcher(msgq, self.controller, MSG_KEY)
        #create window
        self.win = fftwin.fft_window(
            parent=parent,
            controller=self.controller,
            size=size,
            title=title,
            real=self._real,
            fft_size=fft_size,
            baseband_freq=baseband_freq,
            sample_rate_key=SAMPLE_RATE_KEY,
            y_per_div=y_per_div,
            y_divs=y_divs,
            ref_level=ref_level,
            average_key=AVERAGE_KEY,
            avg_alpha_key=AVG_ALPHA_KEY,
            peak_hold=peak_hold,
            msg_key=MSG_KEY,
                        use_persistence=use_persistence,
                        persist_alpha=persist_alpha,
        )
        common.register_access_methods(self, self.win)
        setattr(self.win, 'set_baseband_freq', getattr(self, 'set_baseband_freq')) #BACKWARDS
        setattr(self.win, 'set_peak_hold', getattr(self, 'set_peak_hold')) #BACKWARDS
        #connect
        self.wxgui_connect(self, fft, sink)

class fft_sink_f(_fft_sink_base):
    _fft_chain = blks2.logpwrfft_f
    _item_size = gr.sizeof_float
    _real = True

class fft_sink_c(_fft_sink_base):
    _fft_chain = blks2.logpwrfft_c
    _item_size = gr.sizeof_gr_complex
    _real = False
