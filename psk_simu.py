#!/usr/bin/env python
##################################################
# Communication System Graphical Analyzer
# Author: Dinart Duarte Braga
# Guiding: Edmar Candeia Gurjao
# Description: PSK Channel GUI Analyzer with channel models that includes noise, limited bandwidth and fading
##################################################


##################################################
# Imports
##################################################
import utils, constsink, bersink
from gnuradio import gr
from gnuradio.wxgui import forms
from grc_gnuradio import wxgui as grc_wxgui
import wx
#from numpy import random
import fftsink
import time

class psk_simu(grc_wxgui.top_block_gui):

    def __init__(self):
        grc_wxgui.top_block_gui.__init__(self, title="Communication System Graphical Analyzer (LAPS/UFCG)")
        
        ##################################################
        # Default Variables
        ##################################################
        self.sps = 2
        self.snr = 20
        self.symbol_rate = 140000
        self.mod_type = "DBPSK"
        self.view = 1
        self.band= 200
        self.excess_bw=0.35
        self.fading_flag = False 
        self.fdts = -8
        self.fading_state_rx = False
        
        ##################################################
        # Blocks Definition
        ##################################################
        
        #A bit stream of 1's is generated at the source, scrambled,
        #modulated and sent to the input of an AWGN channel.
        #random.seed(42)
        #self.source = gr.vector_source_b([random.randint(0, 2) for i in range(0,10^8)], True)
        self.source = gr.vector_source_b((1,), True, 1)
        self.thottle = gr.throttle(gr.sizeof_char,10e5)
        self.scrambler = gr.scrambler_bb(0x40801, 0x92F72, 20) #Taxa de simbolos constante
        self.pack = gr.unpacked_to_packed_bb(1, gr.GR_MSB_FIRST)
        self.modulator = utils.mods[self.mod_type](self.sps,excess_bw=self.excess_bw)
        self.channel = utils.channel(1/10.0**(self.snr/10.0),self.band,self.symbol_rate,self.sps)
        
        #The noisy signal is demodulated, descrambled and the BER
        #is estimated by the ber_estim block using the receiver
        #density of 0 bits.
        self.demodulator = utils.demods[self.mod_type](self.sps,excess_bw=self.excess_bw)     
        self.descrambler = gr.descrambler_bb(0x40801, 0x92F72, 20)
        self.char2float = gr.char_to_float()
        self.mov_average = gr.moving_average_ff(524288, 1/524288., 10000)
        self.ber = utils.ber_estim()
        #self.ber = utils.ber_estim_simple(3)

        
        ##################################################
        # GUI Elements Definition
        ##################################################
        
        #Defines an adds FFT Window to GUI
        self.fft = fftsink.fft_sink_c(self.GetWin(), sample_rate=self.symbol_rate*self.sps, baseband_freq=5e6)
        self.GridAdd(self.fft.win, 0,3,4,3)
        self.ctr= gr.complex_to_real(1)
        
        #Defines and adds SNR slider to GUI
        _snr_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._snr_text_box = forms.text_box(parent=self.GetWin(),
            sizer=_snr_sizer, value=self.snr, callback=self.callback_snr,
            label=" SNR (dB)", converter=forms.float_converter(),
            proportion=0)
        self._snr_slider = forms.slider(parent=self.GetWin(),
            sizer=_snr_sizer, value=self.snr, callback=self.callback_snr,
            minimum=0, maximum=20, style=wx.RA_HORIZONTAL, proportion=1)
        self.GridAdd(_snr_sizer, 4, 3, 1, 3)
        
        #Defines and adds bandwidth slider to GUI
        band_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.band_text_box = forms.text_box(parent=self.GetWin(),
            sizer=band_sizer, value=self.band, callback=self.callback_band,
            label="Bandwidth (kHz)", converter=forms.float_converter(),
            proportion=0)
        self.band_slider = forms.slider(parent=self.GetWin(),
            sizer=band_sizer, value=self.band, callback=self.callback_band,
            minimum=30, maximum=200, style=wx.RA_HORIZONTAL, proportion=1)
        self.GridAdd(band_sizer, 5, 3, 1, 3)
        
        #Defines and adds Rayleigh GUI elements
        
        fading_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fading_text_box = forms.text_box(parent=self.GetWin(),
            sizer=fading_sizer, value=self.fdts, callback=self.callback_fading,
            label='Fading/log(FdTs)', converter=forms.float_converter(),
            proportion=0)
        self.fading_slider = forms.slider(parent=self.GetWin(),
            sizer=fading_sizer, value=self.fdts, callback=self.callback_fading,
            minimum=-8, maximum=-2, style=wx.RA_HORIZONTAL, proportion=1)
        self.GridAdd(fading_sizer, 6, 3, 1, 3)
        
        #Defines and adds modulation type chooser to GUI
        self._mod_type_chooser = forms.radio_buttons(parent=self.GetWin(),
            value=self.mod_type, callback=self.set_mod_type,
            label="Modulation", choices=["DBPSK", "DQPSK", "D8PSK"],
            labels=["DBPSK", "DQPSK", "D8PSK"], style=wx.RA_HORIZONTAL)
        self.GridAdd(self._mod_type_chooser, 7, 4, 1, 2)

        
        #Defines and adds signal source chooser
        self.sig_src_chooser = forms.radio_buttons(parent=self.GetWin(),
            value=self.view, callback=self.callback_view,
            label="Signal Source", choices=[0,1],
            labels=["Transmitter","Receiver"], style=wx.RA_VERTICAL)
        self.GridAdd(self.sig_src_chooser, 7,3,1,1)
        
        
        #Definition of the of constellation window and attachment to the GUI
        self.constel = constsink.const_sink_c(self.GetWin(),
            title="RX Constellation Plot",  sample_rate=self.symbol_rate,
            const_size=256, mod=self.mod_type)
        self.GridAdd(self.constel.win,0,0,8,3)
        
        
        #Definition of the constellation sink window and attachment to the GUI
        self.number_sink = bersink.number_sink_f(self.GetWin(),
            sample_rate=self.symbol_rate)
        self.GridAdd(self.number_sink.win,8,0,1,6)
        
        ##################################################
        # Blocks Connections
        ##################################################
        
        #The necessary block connections to the system work as described above.
        self.connect(self.source, self.scrambler , self.thottle, self.pack)
        #self.connect(self.source , self.thottle, self.pack)
        self.connect(self.pack, self.modulator, self.channel, self.demodulator)
        self.connect(self.channel, self.fft)
        self.connect(self.demodulator.diffdec, self.constel)
        self.connect(self.demodulator, self.descrambler, self.char2float, self.mov_average)
        self.connect(self.mov_average, self.ber, self.number_sink)
        
##################################################
# Callback Functions of GUI Elements
##################################################
        
#Callback function of SNR slider, sets the Signal to Noise ratio
#of the AWGN Channel       
        
    def callback_snr(self,snr):
        #if snr > 30:
        #    self.snr = 30
        #elif snr < -10:
        #    self.snr = -10
        #else:
        self.snr = snr;
        self._snr_slider.set_value(self.snr)
        self._snr_text_box.set_value(self.snr)
        self.channel.set_snr(self.snr,self.view)   
        
#Callback function of bandwidth slider.
        
    def callback_band(self,band):
        if band > 300:
            self.band = 300
        elif band < 30:
            self.band = 30
        else:
            self.band = band;
        self.band_slider.set_value(self.band)
        self.band_text_box.set_value(self.band)
        self.channel.set_band(self.band)
        
#Callback function that changes fading level

    def callback_fading(self, fdts):
        self.fdts=fdts
        self.channel.set_fading(fdts)
        self.fading_slider.set_value(fdts)
        self.fading_text_box.set_value(fdts)

#Callback function of the signal source chooser
        
    def callback_view(self,view):
        self.view = view;
        self.sig_src_chooser.set_value(self.view)
        self.callback_snr(self.snr)
        if not view:
            self.channel.set_fading(-8)
            self.channel.set_band(240)
            self._snr_slider.Disable(True)
            self._snr_text_box.Disable(True)
            self.band_slider.Disable(True)
            self.band_text_box.Disable(True)
            self.fading_text_box.Disable(True)
            self.fading_slider.Disable(True)
            self.constel.win.plotter.set_title('TX Constellation Plot')
            self.fft.win.change_yperdiv(30)
        if view:
            self.channel.set_fading(self.fdts)
            self.channel.set_band(self.band)
            self._snr_slider.Disable(False)
            self._snr_text_box.Disable(False)
            self.band_slider.Disable(False)
            self.band_text_box.Disable(False)
            self.fading_text_box.Disable(False)
            self.fading_slider.Disable(False)
            self.constel.win.plotter.set_title('RX Constellation Plot')
            self.fft.win.change_yperdiv(20)
        time.sleep(.05)

#Callback function of the modulation type chooser, it blocks the
#flowgraph and changes modulator and demodulator, it also sets
#the M parameter of the Constellation Sink.
    def set_mod_type(self, mod_type):
        self.mod_type = mod_type
        self._mod_type_chooser.set_value(self.mod_type)

        self.lock()
        
        self.disconnect(self.pack, self.modulator)
        self.disconnect(self.modulator, self.channel)
        self.modulator = utils.mods[self.mod_type](self.sps,excess_bw=self.excess_bw) 
        self.connect(self.pack, self.modulator)
        self.connect(self.modulator, self.channel)

        self.disconnect(self.channel, self.demodulator)
        self.disconnect(self.demodulator.diffdec, self.constel)
        self.disconnect(self.demodulator, self.descrambler)
        self.demodulator = utils.demods[self.mod_type](self.sps,excess_bw=self.excess_bw) 
        
        self.constel.change_mod(self.mod_type)
        
        self.connect(self.channel, self.demodulator)
        self.connect(self.demodulator.diffdec, self.constel)
        self.connect(self.demodulator, self.descrambler)
        self.unlock()
        time.sleep(0.1)
        
if __name__ == '__main__':
    tb = psk_simu()
    tb.Run()