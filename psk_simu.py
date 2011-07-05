#!/usr/bin/env python
##################################################
# PSK Educational Simulator
# Author: Dinart Duarte Braga
# Description: A simulator of a filtered AWGN channel PSK modulated communication system
#              for educational purpose use.
##################################################


import utils, constsink, bersink
from gnuradio import gr
from gnuradio.wxgui import forms
from grc_gnuradio import wxgui as grc_wxgui
from gnuradio.wxgui import fftsink2
import wx
from numpy import random
import fftsink
import time

class psk_simu(grc_wxgui.top_block_gui):

    def __init__(self):
        grc_wxgui.top_block_gui.__init__(self, title="PSK Channel Simulator (by Dinart @LAPS/UFCG)")
        
        ##################################################
        # Default Variables
        ##################################################
        self.sps = 2
        self.snr = 10
        self.samp_rate = 140000
        self.mod_type = "DBPSK"
        self.symb_energy = 1
        self.view = 1
        self.band= 100
        self.excess_bw=0.35
        self.fading_flag = False 
        self.ray_sigma = 0.5
        
        ##################################################
        # Blocks Definition
        ##################################################
        
        #A bit stream of 1's is generated at the source, scrambled,
        #modulated and sent to the input of an AWGN channel.
        #random.seed(42)
        #self.source = gr.vector_source_b([random.randint(0, 2) for i in range(0,10^8)], True)
        self.source = gr.vector_source_b((1,), True, 1)
        self.thottle = gr.throttle(gr.sizeof_char,10e5)
        self.scrambler = gr.scrambler_bb(0x8A, 0x80, 3) #Taxa de simbolos constante
        self.pack = gr.unpacked_to_packed_bb(1, gr.GR_MSB_FIRST)
        self.modulator = utils.mods[self.mod_type](self.sps,excess_bw=self.excess_bw)        
        self.amp = gr.multiply_const_vcc((self.symb_energy, ))
        self.channel = utils.channel(self.symb_energy/10.0**(self.snr/10.0))
        
        #The noisy signal is demodulated, descrambled and the BER
        #is estimated by the ber_estim block using the receiver
        #density of 0 bits.
        self.demodulator = utils.demods[self.mod_type](self.sps,excess_bw=self.excess_bw)     
        self.descrambler = gr.descrambler_bb(0x8A, 0x80, 3)
        self.char2float = gr.char_to_float()
        self.mov_average1 = gr.moving_average_ff(524288, 1/524288., 10000)
        self.mov_average2 = gr.moving_average_ff(524288, 1/524288., 10000)
        self.unpack = gr.packed_to_unpacked_bb(1, gr.GR_LSB_FIRST)
        self.ber = utils.ber_estim()

        
        ##################################################
        # GUI Elements Definition
        ##################################################
        
        #Defines an adds FFT Window to GUI
        self.fft = fftsink.fft_sink_c(self.GetWin(), sample_rate=self.samp_rate*self.sps)
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
            minimum=30, maximum=100, style=wx.RA_HORIZONTAL, proportion=1)
        self.GridAdd(band_sizer, 5, 3, 1, 3)
        
        #Definition of Rayleigh GUI elements
        self.fading_check = forms.check_box(
            parent=self.GetWin(),
            value=self.fading_flag,
            callback=self.toogle_fading,
            label='Fading',
            true=True,
            false=False,
        )
        self.GridAdd(self.fading_check,6, 3, 1, 1)
        
        fading_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fading_text_box = forms.text_box(parent=self.GetWin(),
            sizer=fading_sizer, value=self.ray_sigma, callback=self.set_fading,
            label='Sigma', converter=forms.float_converter(),
            proportion=0)
        self.fading_slider = forms.slider(parent=self.GetWin(),
            sizer=fading_sizer, value=self.ray_sigma, callback=self.set_fading,
            minimum=0, maximum=1, style=wx.RA_HORIZONTAL, proportion=1)
        self.GridAdd(fading_sizer, 6, 4, 1, 2)
        self.fading_slider.Disable(self.toogle_fading)
        self.fading_text_box.Disable(self.toogle_fading)
        
        #Defines and adds modulation type chooser to GUI
        self._mod_type_chooser = forms.radio_buttons(parent=self.GetWin(),
            value=self.mod_type, callback=self.set_mod_type,
            label="Modulation", choices=["DBPSK", "DQPSK", "D8PSK"],
            labels=["DBPSK", "DQPSK", "D8PSK"], style=wx.RA_HORIZONTAL)
        self.GridAdd(self._mod_type_chooser, 7, 4, 1, 2)

        
        #Defines and adds signal chooser
        self.sig_src_chooser = forms.radio_buttons(parent=self.GetWin(),
            value=self.view, callback=self.callback_view,
            label="Signal Source", choices=[0,1],
            labels=["Transmitter","Receiver"], style=wx.RA_VERTICAL)
        self.GridAdd(self.sig_src_chooser, 7,3,1,1)
        
        
        #Definition of the of constellation window and attachment to the GUI
        self.constel = constsink.const_sink_c(self.GetWin(),
            title="RX Constellation Plot",  sample_rate=self.samp_rate,
            M = utils.M[self.mod_type], symbol_rate=self.samp_rate/float(self.sps),
            const_size=256)
        self.GridAdd(self.constel.win,0,0,8,3)
        
        
        #Definition of the constellation sink window and attachment to the GUI
        self.number_sink = bersink.number_sink_f(self.GetWin(),
            sample_rate=self.samp_rate)
        self.GridAdd(self.number_sink.win,8,0,1,6)
        
        ##################################################
        # Blocks Connections
        ##################################################
        
        #The necessary block connections to the system work as described above.
        self.connect(self.source, self.scrambler , self.thottle, self.pack)
        #self.connect(self.source , self.thottle, self.pack)
        self.connect(self.pack, self.modulator, self.amp, self.channel, self.demodulator)
        self.connect(self.channel, self.fft)
        self.connect(self.demodulator.rrc_filter, self.constel)
        self.connect(self.demodulator, self.descrambler, self.char2float, self.mov_average1)
        self.connect(self.mov_average1, self.mov_average2, self.ber, self.number_sink)
        
        ##################################################
        # Callback Functions of GUI Elements
        ##################################################
        
        #Callback function of SNR slider, sets the Signal to Noise ratio
        #of the AWGN Channel
    def set_snr(self, snr, view):
        self.channel.set_noise_voltage(view*self.symb_energy/10.0**(snr/10.0))
        
        
    def callback_snr(self,snr):
        if snr > 30:
            self.snr = 30
        elif snr < -10:
            self.snr = -10
        else:
            self.snr = snr;
        self._snr_slider.set_value(self.snr)
        self._snr_text_box.set_value(self.snr)
        self.set_snr(self.snr,self.view)    
        
    def callback_band(self,band):
        if band > 100:
            self.band = 100
        elif band < 30:
            self.band = 30
        else:
            self.band = band;
        self.band_slider.set_value(self.band)
        self.band_text_box.set_value(self.band)
        self.channel.setband(self.band)
        
    def callback_view(self,view):
        self.view = view;
        self.sig_src_chooser.set_value(self.view)
        self.set_snr(self.snr,self.view)
        if not view:
            self._snr_slider.Disable(True)
            self._snr_text_box.Disable(True)
            self.band_slider.Disable(True)
            self.band_text_box.Disable(True)
            self.fading_check.Disable(True)
            self.fading_text_box.Disable(True)
            self.constel.win.plotter.set_title('TX Constellation Plot')
            self.fft.win.change_yperdiv(30)
            if(self.fading_flag):
                self.fading_flag = False
                self.fading_check.set_value(self.fading_flag)
        if view:
            self._snr_slider.Disable(False)
            self._snr_text_box.Disable(False)
            self.band_slider.Disable(False)
            self.band_text_box.Disable(False)
            self.fading_check.Disable(False)
            self.constel.win.plotter.set_title('RX Constellation Plot')
            self.fft.win.change_yperdiv(20)
        time.sleep(.1)

        #Callback function of the modulation type chooser, it blocks the
        #flowgraph and changes modulator and demodulator, it also sets
        #the M parameter of the Constellation Sink.
    def set_mod_type(self, mod_type):
        self.mod_type = mod_type
        self._mod_type_chooser.set_value(self.mod_type)

        self.lock()
        
        self.disconnect(self.pack, self.modulator)
        self.disconnect(self.modulator, self.amp)
        self.modulator = utils.mods[self.mod_type](self.sps,excess_bw=self.excess_bw) 
        self.connect(self.pack, self.modulator)
        self.connect(self.modulator, self.amp)

        self.disconnect(self.channel, self.demodulator)
        self.disconnect(self.demodulator.rrc_filter, self.constel)
        self.disconnect(self.demodulator, self.descrambler)
        self.demodulator = utils.demods[self.mod_type](self.sps,excess_bw=self.excess_bw) 
        
        self.constel.change_M(utils.M[self.mod_type])
        
        self.connect(self.channel, self.demodulator)
        self.connect(self.demodulator.rrc_filter, self.constel)
        self.connect(self.demodulator, self.descrambler)
        self.unlock()
        time.sleep(.1)
    
    def toogle_fading(self, flag):
        self.fading_flag = flag
        self.channel.toggle_fading(flag,self.ray_sigma)
        self.fading_slider.Disable(not self.fading_flag)
        self.fading_text_box.Disable(not self.fading_flag)
        
        
    def set_fading(self, ray_sigma):
        self.ray_sigma=ray_sigma
        self.channel.set_fading(ray_sigma)
        self.fading_slider.set_value(self.ray_sigma)
        self.fading_text_box.set_value(self.ray_sigma)
        
if __name__ == '__main__':
    tb = psk_simu()
    tb.Run()