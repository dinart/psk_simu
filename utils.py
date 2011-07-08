##################################################
# Communication System Graphical Analyzer
# Author: Dinart Duarte Braga
# Guiding: Edmar Candeia Gurjao
# Description: This file contains useful classes to be used in the main program
##################################################


##################################################
# Imports
##################################################
from gnuradio import gr, blks2
import numpy


##################################################
# Dictionaries used to help control functions
##################################################
mods = {'DBPSK':blks2.dbpsk_mod, 'DQPSK':blks2.dqpsk_mod, 'D8PSK':blks2.d8psk_mod }
demods = {'DBPSK':blks2.dbpsk_demod, 'DQPSK':blks2.dqpsk_demod, 'D8PSK':blks2.d8psk_demod }
k = {'DBPSK':1, 'DQPSK':2, 'D8PSK':3}
M = {'DBPSK':2, 'DQPSK':4, 'D8PSK':8}
gain = {'DBPSK':0.87, 'DQPSK':0.68, 'D8PSK':27000}

#Channel Model (AWGN + Filter)
#Rayleigh scattering is added dynamically.
class channel(gr.hier_block2):
    def __init__(self,ampl_i,band=0):
        gr.hier_block2.__init__(self,"Channel",
                                gr.io_signature(1,1,gr.sizeof_gr_complex),
                                gr.io_signature(1,1,gr.sizeof_gr_complex))
        self.adder = gr.add_cc()
        self.noise = gr.noise_source_c(gr.GR_GAUSSIAN, 1, -42)
        self.ampl = gr.multiply_const_cc(ampl_i)
        self.taps = gr.firdes.low_pass_2 (1,560,band/2,5,80,gr.firdes.WIN_KAISER)
        self.filter=gr.interp_fir_filter_ccf(1, self.taps)
        self.fading = False
        
        #Connects
        self.connect(self,self.filter,(self.adder,0))
        self.connect(self.noise, self.ampl, (self.adder,1))
        self.connect(self.adder, self)

    def toggle_filter(self,flag):
        if(flag):
            self.filter.set_taps(self.taps)
        else:
            self.filter.set_taps([1])
            
        
        
#function that toggles fading on and off
    def toggle_fading(self,flag,coe_time):
        self.lock()
        if (flag):
            self.disconnect(self,self.filter)
            band=1e3/coe_time
            self.ray = gr.noise_source_c(gr.GR_GAUSSIAN, 1, -42);
            self.ray.set_amplitude(0.7)
            self.mag = gr.complex_to_mag(1)
            self.taps_lp = gr.firdes.low_pass_2 (1,560,band,5,80,gr.firdes.WIN_KAISER)
            self.taps_gau = gr.firdes.gaussian(1,2,0.675,20)
            self.taps_ray = numpy.convolve(numpy.array(self.taps_gau),numpy.array(self.taps_lp))
            self.filter_ray = gr.interp_fir_filter_fff(1, self.taps_ray)
            self.connect(self.ray,self.mag,self.filter_ray)
            
            self.real = gr.complex_to_real(1)
            self.imag = gr.complex_to_imag(1)
            self.connect(self,self.real)
            self.connect(self,self.imag)
            
            self.prodreal = gr.multiply_ff()
            self.prodimag = gr.multiply_ff()
            self.connect(self.real,(self.prodreal,0))
            self.connect(self.imag,(self.prodimag,0))
            self.connect(self.filter_ray,(self.prodreal,1))
            self.connect(self.filter_ray,(self.prodimag,1))
            
            self.realtocom = gr.float_to_complex(1)
            self.connect(self.prodreal,(self.realtocom,0))
            self.connect(self.prodimag,(self.realtocom,1))
            
            self.connect(self.realtocom, self.filter)
        else:
            self.disconnect(self, self.real)
            self.disconnect(self, self.imag)
            self.disconnect(self.realtocom, self.filter)
            self.connect(self,self.filter)
            
            self.disconnect(self.ray,self.mag, self.filter_ray)
            self.disconnect(self.real,(self.prodreal,0))
            self.disconnect(self.imag,(self.prodimag,0))
            self.disconnect(self.filter_ray,(self.prodreal,1))
            self.disconnect(self.filter_ray,(self.prodimag,1))
            self.disconnect(self.prodreal,(self.realtocom,0))
            self.disconnect(self.prodimag,(self.realtocom,1))
            del(self.ray)
            del(self.mag)
            del(self.real)
            del(self.imag)
            del(self.filter_ray)

            del(self.prodreal)
            del(self.prodimag)
            del(self.realtocom)
               
        self.fading=flag
        self.unlock()
        
##################################################
# Functions that change degradation levels
##################################################

    def set_noise_voltage(self,new_amp):
        self.ampl.set_k(new_amp)
        
    def set_fading(self,coe_time):
        if(self.fading):
            band=1e3/coe_time
            self.taps_lp = gr.firdes.low_pass_2 (1,560,band,5,80,gr.firdes.WIN_KAISER)
            self.taps_gau = gr.firdes.gaussian(1,2,0.675,20)
            self.taps_ray = numpy.convolve(numpy.array(self.taps_gau),numpy.array(self.taps_lp))
            self.filter_ray.set_taps(self.taps_ray)
        
    
    def setband(self,band):
        #self.disconnect(self,self.filter)
        #self.disconnect(self.filter,(self.adder,0))
        self.taps = gr.firdes.low_pass_2 (1,560,band/2,5,80,gr.firdes.WIN_KAISER)
        self.filter.set_taps(self.taps)
        #self.filter=gr.interp_fir_filter_ccf(1, self.taps)
        #self.connect(self,self.filter)
        #self.connect(self.filter,(self.adder,0))
        
#TODO: Implement Jakes model to fading. Current model is good only for small Tcs.
class rayleigh(gr.hier_block2):
    def __init__(self,ampl_i,band=0):
        gr.hier_block2.__init__(self,"AWGN Channel",
                                gr.io_signature(1,1,gr.sizeof_gr_complex),
                                gr.io_signature(1,1,gr.sizeof_gr_complex))
        self.noise = gr.noise_source_c(gr.GR_GAUSSIAN, 1, -42)
        self.taps = gr.firdes.low_pass_2 (1,280,95,5,60,gr.firdes.GAUSSIAN)
        pass  
        

#BER estimation using a quadratic polynomial, it results on more accuracy
#approximations for BER > 10%, compared to dividing the descrambled density
#of 0's by 3.
class ber_estim(gr.hier_block2):
    def __init__(self):

        gr.hier_block2.__init__(self,"BER Estimator",
                                gr.io_signature(1,1,gr.sizeof_float),
                                gr.io_signature(1,1,gr.sizeof_float))
        
        #TODO Implement a polynomial block in C++ and approximate with polynomials
        #of arbitrary order
        self.add = gr.add_const_vff((-1, ))
        self.square = gr.multiply_ff()
        self.mult_lin = gr.multiply_const_ff(-0.20473967)
        self.mult_sq = gr.multiply_const_ff(1.5228658)
        self.sum = gr.add_ff()
        self.connect(self,self.add)
        self.connect(self.add,(self.square,0))
        self.connect(self.add,(self.square,1))
        self.connect(self.square,self.mult_sq,(self.sum,0))
        self.connect(self.add,self.mult_lin,(self.sum,1))
        self.connect(self.sum,self)
        
#Simple BER estimator proposed by GNURadio example. Very bad for BER > 10%
class ber_estim_simple(gr.hier_block2):
    def __init__(self,k):

        gr.hier_block2.__init__(self,"BER Estimator",
                                gr.io_signature(1,1,gr.sizeof_float),
                                gr.io_signature(1,1,gr.sizeof_float))
        
        self.add = gr.add_const_vff((-1, ))
        self.mult= gr.multiply_const_ff(-1/k)
        self.connect(self,self.add, self.mult,self)