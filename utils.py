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
import numpy, math


##################################################
# Dictionaries used to help control functions
##################################################
mods = {'DBPSK':blks2.dbpsk_mod, 'DQPSK':blks2.dqpsk_mod, 'D8PSK':blks2.d8psk_mod }
demods = {'DBPSK':blks2.dbpsk_demod, 'DQPSK':blks2.dqpsk_demod, 'D8PSK':blks2.d8psk_demod }
k = {'DBPSK':1, 'DQPSK':2, 'D8PSK':3}
M = {'DBPSK':2, 'DQPSK':4, 'D8PSK':8}
gain = {'DBPSK':1, 'DQPSK':1, 'D8PSK':270}

#Channel Model (AWGN + Filter)
#Rayleigh scattering is added dynamically.
class channel(gr.hier_block2):
    def __init__(self,ampl_i,band,symbol_rate,sps):
        gr.hier_block2.__init__(self,"Channel",
                                gr.io_signature(1,1,gr.sizeof_gr_complex),
                                gr.io_signature(1,1,gr.sizeof_gr_complex))
        
        self.symbol_rate = symbol_rate
        self.sample_rate=symbol_rate*sps
        self.fading = False
        self.adder = gr.add_cc()
        self.noise = gr.noise_source_c(gr.GR_GAUSSIAN, 1, -42)
        self.ampl = gr.multiply_const_cc(ampl_i)
        self.taps = gr.firdes.low_pass_2 (1,280,band/2,5,80,gr.firdes.WIN_KAISER)
        self.filter=gr.fir_filter_ccf(1,self.taps)
        
        #Connects
        self.connect(self,self.filter,(self.adder,0))
        self.connect(self.noise, self.ampl, (self.adder,1))
        self.connect(self.adder, self)

           
    def toggle_fading(self,flag,fd):
        self.lock()
        
        if(flag):
            self.disconnect(self,self.filter)
            self.ray=rayleigh(fd,5,self.sample_rate)
            self.connect(self,self.ray,self.filter)     
            self.fading=True                
            
        else:
            if(self.fading):
                self.disconnect(self,self.ray,self.filter)
                del(self.ray)
                self.connect(self,self.filter)
                self.fading=False
            
        self.unlock()
            
    def set_fading(self,fdts):
        fd= 10**fdts*self.symbol_rate
        #fd= fdts/100*self.symbol_rate
        if(fd > 10**-7*self.symbol_rate):
            if(not self.fading):
                self.toggle_fading(True,fd)
            else:
                self.ray.set_fd(fd)
        else:
            self.toggle_fading(False,fd)
            
    def set_snr(self, snr, view):
        self.ampl.set_k(view*(1/10.0**(snr/10.0)))
        
    def setband(self,band):
            self.taps = gr.firdes.low_pass_2 (1,280,band/2,5,80,gr.firdes.WIN_KAISER)
            self.filter.set_taps(self.taps)
        
        
#Jakes Model for Fading Generation
class rayleigh(gr.hier_block2):
    def __init__(self,fd,M,sample_rate):
        gr.hier_block2.__init__(self,"Rayleigh Channel",
                                gr.io_signature(1,1,gr.sizeof_gr_complex),
                                gr.io_signature(1,1,gr.sizeof_gr_complex))
        
        self.M = M
        self.sample_rate = sample_rate
        n=range(1,M+1)
        N = 4*M+2
        
        f_n= [fd*math.cos(2*math.pi*x/N) for x in n]
                
        beta_n = [math.pi/M*x for x in n]
        
        a_n = [2*math.cos(x) for x in beta_n]
        a_n.append(math.sqrt(2)*math.cos(math.pi/4))
        a_n = [x*2/math.sqrt(N) for x in a_n]
        
        
        b_n= [2*math.sin(x) for x in beta_n]
        b_n.append(math.sqrt(2)*math.sin(math.pi/4))
        b_n = [x*2/math.sqrt(N) for x in b_n]
        
        f_n.append(fd)
                
        self.sin_real = [gr.sig_source_f(self.sample_rate,gr.GR_COS_WAVE,f_n[i],a_n[i]) for i in range(M+1)]
        self.sin_imag = [gr.sig_source_f(self.sample_rate,gr.GR_COS_WAVE,f_n[i],b_n[i]) for i in range(M+1)]
            
        self.add_real = gr.add_ff(1)
        self.add_imag = gr.add_ff(1)
        
        for i in range (M+1):
            self.connect(self.sin_real[i],(self.add_real,i))
  
        for i in range (M+1):
            self.connect(self.sin_imag[i],(self.add_imag,i))          
            
        self.ftoc = gr.float_to_complex(1)
        
        self.connect(self.add_real,(self.ftoc,0))
        self.connect(self.add_imag,(self.ftoc,1))
        self.mulc = gr.multiply_const_cc((0.5))
        
        #self.divide = gr.divide_cc(1)
        #self.connect(self,(self.divide,0))
        #self.connect(self.ftoc,(self.divide,1))
        #self.connect(self.divide, self)
        self.prod = gr.multiply_cc(1)
        self.connect(self,(self.prod,0))
        self.connect(self.ftoc,self.mulc,(self.prod,1))
        self.connect(self.prod, self)
        
    def set_fd(self,fd):
        M = self.M
        n=range(1,M+1)
        N = 4*M+2
        
        f_n= [fd*math.cos(2*math.pi*x/N) for x in n]
                
        beta_n = [math.pi/M*x for x in n]
        
        a_n = [2*math.cos(x) for x in beta_n]
        a_n.append(math.sqrt(2)*math.cos(math.pi/4))
        a_n = [x*2/math.sqrt(N) for x in a_n]
        
        
        b_n= [2*math.sin(x) for x in beta_n]
        b_n.append(math.sqrt(2)*math.sin(math.pi/4))
        b_n = [x*2/math.sqrt(N) for x in b_n]
        
        f_n.append(fd)
        
        for i in range(M+1):
            self.sin_real[i].set_amplitude(a_n[i])
            self.sin_imag[i].set_amplitude(b_n[i])
            self.sin_real[i].set_frequency(f_n[i])
            self.sin_imag[i].set_frequency(f_n[i])
   

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