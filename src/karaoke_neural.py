"""Bounded UVR/MDX inference and streaming overlap blending, outside GTK.

Weights and framing: UVR_MDXNET_9482, UVR model_data MD5
0ddfc0eb5792638ad5dc27850236c246: FFT6144, dim_f2048, hop1024,
vocals, compensation1.035. UVR authors permit third-party model use under MIT
with credit; see docs/THIRD_PARTY_KARAOKE.md.
"""
import math
import time
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import resample_poly
from karaoke_model import verified_model

RATE=48000
MODEL_RATE=44100
FFT=6144
HOP=1024
FRAMES=64
FREQUENCIES=2048
MODEL_SAMPLES=(FRAMES-1)*HOP
WINDOW_SAMPLES=math.ceil(MODEL_SAMPLES*160/147)
LOOKAHEAD=8192
OVERLAP=2048


def stft(pcm):
    window=np.hanning(FFT+1)[:-1].astype(np.float32)
    padded=np.pad(pcm,((0,0),(FFT//2,FFT//2)),mode='reflect')
    frames=sliding_window_view(padded,FFT,axis=1)[:,::HOP,:]*window
    spectrum=np.fft.rfft(frames,axis=-1).transpose(0,2,1)
    return np.stack((spectrum[0].real,spectrum[0].imag,spectrum[1].real,spectrum[1].imag))[None].astype(np.float32)


def istft(tensor):
    frames=tensor.shape[-1];bins=FFT//2+1
    spec=np.zeros((2,bins,frames),np.complex64)
    spec[0,:tensor.shape[1]]=tensor[0]+1j*tensor[1]
    spec[1,:tensor.shape[1]]=tensor[2]+1j*tensor[3]
    window=np.hanning(FFT+1)[:-1].astype(np.float32)
    waves=np.fft.irfft(spec,n=FFT,axis=1)*window[None,:,None]
    length=FFT+(frames-1)*HOP
    result=np.zeros((2,length),np.float32);weight=np.zeros(length,np.float32)
    for i in range(frames):
        offset=i*HOP;result[:,offset:offset+FFT]+=waves[:,:,i];weight[offset:offset+FFT]+=window**2
    result/=np.maximum(weight,1e-8)
    return result[:,FFT//2:-FFT//2]


class NeuralSeparator:
    def __init__(self,model=None,session=None):
        if session is None:
            import onnx,onnxruntime as ort
            graph=onnx.load(str(model or verified_model()))
            # This convolutional model accepts shorter time windows. Only I/O
            # shape declarations change; learned tensors remain byte-identical.
            for item in (*graph.graph.input,*graph.graph.output):item.type.tensor_type.shape.dim[3].dim_value=FRAMES
            options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
            options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
            options.add_session_config_entry('session.intra_op.allow_spinning','0')
            self.session=ort.InferenceSession(graph.SerializeToString(),options,providers=['CPUExecutionProvider'])
        else:self.session=session
        self.input=self.session.get_inputs()[0].name

    def vocals(self,pcm):
        if pcm.shape!=(WINDOW_SAMPLES,2):raise ValueError('Wrong AI context length')
        if np.max(np.abs(pcm))<1e-7:return np.zeros_like(pcm)
        audio=resample_poly(pcm.T,147,160,axis=1)[:,:MODEL_SAMPLES].astype(np.float32)
        spectrum=stft(audio)[:,:,:FREQUENCIES,:].copy();spectrum[:,:,:3,:]=0
        prediction=self.session.run(None,{self.input:spectrum})[0]
        if prediction.shape!=(1,4,FREQUENCIES,FRAMES) or not np.isfinite(prediction).all():
            raise RuntimeError('ai-invalid-output')
        voice=istft(prediction[0])*1.035
        return resample_poly(voice,160,147,axis=1).T[:WINDOW_SAMPLES].astype(np.float32)

    def benchmark(self):
        zero=np.random.default_rng(7).normal(0,.002,(WINDOW_SAMPLES,2)).astype(np.float32)
        times=[]
        for _ in range(2):
            start=time.monotonic();self.vocals(zero);times.append(time.monotonic()-start)
        estimate=max(times)
        block=max(32768,math.ceil(estimate*1.65*RATE/1024)*1024)
        if block>51200:raise RuntimeError('ai-too-slow')
        return block,estimate


class NeuralBlocks:
    """Keep past context; infer one future-aware block; blend model estimates.

    No audio is saved. The dry block and predicted vocal always refer to exactly
    the same samples. A zero reduction is an aligned, unchanged stereo block.
    """
    def __init__(self,separator,block,amount=.7):
        self.separator=separator;self.block=block;self.target=float(amount);self.amount=float(amount)
        self.history=np.zeros((WINDOW_SAMPLES,2),np.float32)
        self.first=True;self.ahead=None

    @property
    def required(self):return self.block+LOOKAHEAD if self.first else self.block

    def process(self,incoming):
        count=self.required
        if incoming.shape!=(count,2):raise ValueError('Wrong streaming block length')
        self.history[:-count]=self.history[count:];self.history[-count:]=incoming
        voice=self.separator.vocals(self.history)
        begin=WINDOW_SAMPLES-LOOKAHEAD-self.block;end=begin+self.block
        predicted=voice[begin:end].copy()
        if self.ahead is not None:
            weight=np.linspace(0,1,OVERLAP,dtype=np.float32)[:,None]
            predicted[:OVERLAP]=self.ahead*(1-weight)+predicted[:OVERLAP]*weight
        self.ahead=voice[end:end+OVERLAP].copy()
        # Strength follows the physical dial smoothly across a whole block.
        ramp=(self.target+(self.amount-self.target)*np.exp(-np.arange(self.block)/RATE/.085)).astype(np.float32)
        self.amount=float(ramp[-1]);self.first=False
        return np.clip(self.history[begin:end]-ramp[:,None]*predicted,-1,1).astype('<f4')
