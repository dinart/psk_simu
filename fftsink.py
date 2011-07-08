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
from gnuradio.wxgui import common, forms
from gnuradio import gr, blks2, gr
from gnuradio.wxgui.pubsub import pubsub
from gnuradio.wxgui.constants import *
import math
from gnuradio.wxgui import plotter
from gnuradio.wxgui import common
import wx
import numpy

##################################################
# Constants
##################################################
SLIDER_STEPS = 100
AVG_ALPHA_MIN_EXP, AVG_ALPHA_MAX_EXP = -3, 0
PERSIST_ALPHA_MIN_EXP, PERSIST_ALPHA_MAX_EXP = -2, 0
DEFAULT_WIN_SIZE = (450, 270)
DEFAULT_FRAME_RATE = gr.prefs().get_long('wxgui', 'fft_rate', 30)
DB_DIV_MIN, DB_DIV_MAX = 1, 40
FFT_PLOT_COLOR_SPEC = (0.3, 0.3, 1.0)
PEAK_VALS_COLOR_SPEC = (0.0, 0.8, 0.0)
EMPTY_TRACE = list()
TRACES = ('A', 'B')
TRACES_COLOR_SPEC = {
    'A': (1.0, 0.0, 0.0),
    'B': (0.8, 0.0, 0.8),
}

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
        title='Frequency Domain',
        size=DEFAULT_WIN_SIZE,
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
        self.win = fft_window(
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


##################################################
# FFT window control panel
##################################################
class control_panel(wx.Panel):
    """
    A control panel with wx widgits to control the plotter and fft block chain.
    """

    def __init__(self, parent):
        """
        Create a new control panel.
        @param parent the wx parent window
        """
        self.parent = parent
        wx.Panel.__init__(self, parent, style=wx.SUNKEN_BORDER)
        parent[SHOW_CONTROL_PANEL_KEY] = True
       
        #mouse wheel event
        def on_mouse_wheel(event):
            if event.GetWheelRotation() < 0: self._on_incr_ref_level(event)
            else: self._on_decr_ref_level(event)
        parent.plotter.Bind(wx.EVT_MOUSEWHEEL, on_mouse_wheel)
        
    def _on_incr_ref_level(self, event):
        self.parent[REF_LEVEL_KEY] = self.parent[REF_LEVEL_KEY] + self.parent[Y_PER_DIV_KEY]
    def _on_decr_ref_level(self, event):
        self.parent[REF_LEVEL_KEY] = self.parent[REF_LEVEL_KEY] - self.parent[Y_PER_DIV_KEY]
    def _on_incr_db_div(self, event):
        self.parent[Y_PER_DIV_KEY] = min(DB_DIV_MAX, common.get_clean_incr(self.parent[Y_PER_DIV_KEY]))
    def _on_decr_db_div(self, event):
        self.parent[Y_PER_DIV_KEY] = max(DB_DIV_MIN, common.get_clean_decr(self.parent[Y_PER_DIV_KEY]))
            

    ##################################################
    # subscriber handlers
    ##################################################
        def _update_layout(self,key):
          # Just ignore the key value we get
          # we only need to now that the visability or size of something has changed
          self.parent.Layout()
          #self.parent.Fit()          

##################################################
# FFT window with plotter and control panel
##################################################
class fft_window(wx.Panel, pubsub):
    def __init__(
        self,
        parent,
        controller,
        size,
        title,
        real,
        fft_size,
        baseband_freq,
        sample_rate_key,
        y_per_div,
        y_divs,
        ref_level,
        average_key,
        avg_alpha_key,
        peak_hold,
        msg_key,
                use_persistence,
                persist_alpha,
    ):

        pubsub.__init__(self)
        #setup
        self.samples = EMPTY_TRACE
        self.real = real
        self.fft_size = fft_size
        self._reset_peak_vals()
        self._traces = dict()
        #proxy the keys
        self.proxy(MSG_KEY, controller, msg_key)
        self.proxy(AVERAGE_KEY, controller, average_key)
        self.proxy(AVG_ALPHA_KEY, controller, avg_alpha_key)
        self.proxy(SAMPLE_RATE_KEY, controller, sample_rate_key)
        #initialize values
        self[PEAK_HOLD_KEY] = peak_hold
        self[Y_PER_DIV_KEY] = y_per_div
        self[Y_DIVS_KEY] = y_divs
        self[X_DIVS_KEY] = 8 #approximate
        self[REF_LEVEL_KEY] = ref_level
        self[BASEBAND_FREQ_KEY] = baseband_freq
        self[RUNNING_KEY] = True
        self[USE_PERSISTENCE_KEY] = use_persistence
        self[PERSIST_ALPHA_KEY] = persist_alpha
        for trace in TRACES:
            #a function that returns a function
            #so the function wont use local trace
            def new_store_trace(my_trace):
                def store_trace(*args):
                    self._traces[my_trace] = self.samples
                    self.update_grid()
                return store_trace
            def new_toggle_trace(my_trace):
                def toggle_trace(toggle):
                    #do an automatic store if toggled on and empty trace
                    if toggle and not len(self._traces[my_trace]):
                        self._traces[my_trace] = self.samples
                    self.update_grid()
                return toggle_trace
            self._traces[trace] = EMPTY_TRACE
            self[TRACE_STORE_KEY+trace] = False
            self[TRACE_SHOW_KEY+trace] = False
            self.subscribe(TRACE_STORE_KEY+trace, new_store_trace(trace))
            self.subscribe(TRACE_SHOW_KEY+trace, new_toggle_trace(trace))
        #init panel and plot
        wx.Panel.__init__(self, parent, style=wx.SUNKEN_BORDER)
        self.plotter = plotter.channel_plotter(self)
        self.plotter.SetSize(wx.Size(*size))
        self.plotter.set_title(title)
        self.plotter.enable_legend(True)
        self.plotter.enable_point_label(True)
        self.plotter.enable_grid_lines(True)
        self.plotter.set_use_persistence(use_persistence)
        self.plotter.set_persist_alpha(persist_alpha)
        #setup the box with plot and controls
        main_box = wx.BoxSizer(wx.HORIZONTAL)
        main_box.Add(self.plotter, 1, wx.EXPAND)
        self.SetSizerAndFit(main_box)
        #register events
        self.subscribe(AVERAGE_KEY, self._reset_peak_vals)
        self.subscribe(MSG_KEY, self.handle_msg)
        self.subscribe(SAMPLE_RATE_KEY, self.update_grid)
        for key in (
            BASEBAND_FREQ_KEY,
            Y_PER_DIV_KEY, X_DIVS_KEY,
            Y_DIVS_KEY, REF_LEVEL_KEY,
        ): self.subscribe(key, self.update_grid)
        self.subscribe(USE_PERSISTENCE_KEY, self.plotter.set_use_persistence)
        self.subscribe(PERSIST_ALPHA_KEY, self.plotter.set_persist_alpha)
        #initial update
        self.plotter.enable_point_label(False)
        self.update_grid()
        
    def change_yperdiv(self,val):
        self[Y_PER_DIV_KEY] = val


    def autoscale(self, *args):
        """
        Autoscale the fft plot to the last frame.
        Set the dynamic range and reference level.
        """
        if not len(self.samples): return
        min_level, max_level = common.get_min_max_fft(self.samples)
        #set the range to a clean number of the dynamic range
        self[Y_PER_DIV_KEY] = common.get_clean_num(1+(max_level - min_level)/self[Y_DIVS_KEY])
        #set the reference level to a multiple of y per div
        self[REF_LEVEL_KEY] = self[Y_PER_DIV_KEY]*round(.5+max_level/self[Y_PER_DIV_KEY])

    def _reset_peak_vals(self, *args): self.peak_vals = EMPTY_TRACE

    def handle_msg(self, msg):
        """
        Handle the message from the fft sink message queue.
        If complex, reorder the fft samples so the negative bins come first.
        If real, keep take only the positive bins.
        Plot the samples onto the grid as channel 1.
        If peak hold is enabled, plot peak vals as channel 2.
        @param msg the fft array as a character array
        """
        if not self[RUNNING_KEY]: return
        #convert to floating point numbers
        samples = numpy.fromstring(msg, numpy.float32)[:self.fft_size] #only take first frame
        num_samps = len(samples)
        #reorder fft
        if self.real: samples = samples[:(num_samps+1)/2]
        else: samples = numpy.concatenate((samples[num_samps/2+1:], samples[:(num_samps+1)/2]))
        self.samples = samples
        #peak hold calculation
        if self[PEAK_HOLD_KEY]:
            if len(self.peak_vals) != len(samples): self.peak_vals = samples
            self.peak_vals = numpy.maximum(samples, self.peak_vals)
            #plot the peak hold
            self.plotter.set_waveform(
                channel='Peak',
                samples=self.peak_vals,
                color_spec=PEAK_VALS_COLOR_SPEC,
            )
        else:
            self._reset_peak_vals()
            self.plotter.clear_waveform(channel='Peak')
        #plot the fft
        self.plotter.set_waveform(
            channel='LAPS/UFCG',
            samples=samples,
            color_spec=FFT_PLOT_COLOR_SPEC,
        )
        #update the plotter
        self.plotter.update()

    def update_grid(self, *args):
        """
        Update the plotter grid.
        This update method is dependent on the variables below.
        Determine the x and y axis grid parameters.
        The x axis depends on sample rate, baseband freq, and x divs.
        The y axis depends on y per div, y divs, and ref level.
        """
        for trace in TRACES:
            channel = '%s'%trace.upper()
            if self[TRACE_SHOW_KEY+trace]:
                self.plotter.set_waveform(
                    channel=channel,
                    samples=self._traces[trace],
                    color_spec=TRACES_COLOR_SPEC[trace],
                )
            else: self.plotter.clear_waveform(channel=channel)
        #grid parameters
        sample_rate = self[SAMPLE_RATE_KEY]
        baseband_freq = self[BASEBAND_FREQ_KEY]
        y_per_div = self[Y_PER_DIV_KEY]
        y_divs = self[Y_DIVS_KEY]
        x_divs = self[X_DIVS_KEY]
        ref_level = self[REF_LEVEL_KEY]
        #determine best fitting x_per_div
        if self.real: x_width = sample_rate/2.0
        else: x_width = sample_rate/1.0
        x_per_div = common.get_clean_num(x_width/x_divs)
        #update the x grid
        if self.real:
            self.plotter.set_x_grid(
                baseband_freq,
                baseband_freq + sample_rate/2.0,
                x_per_div, True,
            )
        else:
            self.plotter.set_x_grid(
                baseband_freq - sample_rate/2.0,
                baseband_freq + sample_rate/2.0,
                x_per_div, True,
            )
        #update x units
        self.plotter.set_x_label('Frequency', 'Hz')
        #update y grid
        self.plotter.set_y_grid(ref_level-y_per_div*y_divs, ref_level, y_per_div)
        #update y units
        self.plotter.set_y_label('Amplitude', 'dB')
        #update plotter
        self.plotter.update()
