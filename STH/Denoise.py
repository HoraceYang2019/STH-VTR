# pip install PyWavelets
import numpy as np 
import pywt 
import pandas as pd 

#%% 
def wp_(s, waveletFun='db3', level=3):    
    # Compute the wavelet packet decomposition of the signal s
    wp = pywt.WaveletPacket(data=s, wavelet=waveletFun, maxlevel=level)
    
    # Extract the list of node names at the specified level of the decomposition
    node_space = [node.path for node in wp.get_level(level, 'freq')] # order="natural" or "freq"
    wp_E = []  
    
    # Calculate the energy of each wavelet packet
    for node in node_space:
        E = sum((np.sqrt(wp['%s'%node].data)))   # Compute the energy by summing the square of the values in the node
        wp_E.append(E)
        
    return wp_E     # Return the list of wavelet packet energies

#%% 
    #wden(X,TPTR,SORH,SCAL,N,'wname')
    #    TPTR: threshold selection rule, {rigrsure','heursure','sqtwolog', minimaxi'}
    #    SORH: ('soft' or 'hard') is for soft or hard thresholding
    #    SCAL: defines multiplicative threshold rescaling
    #        'one' for no rescaling
    #        'sln' for rescaling using a single estimation of level noise based on first-level coefficients
    #        'mln' for rescaling done using level-dependent estimation of level noise
    #    N: decomposition level N
    #    'wname': desired orthogonal wavelet, {'db1'-'db45, 'sym2'-'sym45',...}
def wden(x, tptr, sorh, scal, n, wname):
    eps = 2.220446049250313e-16
    coeffs = pywt.wavedec(x, wname, 'sym', n)
    if scal == 'one':
        s = 1
    elif scal == 'sln':
        s = wnoisest(coeffs)
    elif scal == 'mln':
        s = wnoisest(coeffs, level=n)
    else:
        raise ValueError('Invalid value, scal = %s' % (scal))
    coeffsd = [coeffs[0]]
    for i in range(n):
        if tptr == 'sqtwolog' or tptr == 'minimaxi':
            th = thselect(x, tptr)
        else:
            if len(s) == 1:
                if s < np.sqrt(eps) * max(coeffs[1 + i]):
                    th = 0
                else:
                    th = thselect(coeffs[1 + i] / s, tptr)
            else:
                if s[i] < np.sqrt(eps) * max(coeffs[1 + i]):
                    th = 0
                else:
                    th = thselect(coeffs[1 + i] / s[i], tptr)
        if len(s) == 1:
            th = th * s
        else:
            th = th * s[i]
        coeffsd.append(np.array(wthresh(coeffs[1 + i], sorh, th)))
    xdtemp = pywt.waverec(coeffsd, wname, 'sym')
    extlen = int(abs(len(x) - len(xdtemp)) / 2)
    xd = xdtemp[extlen:len(x) + extlen]
    return xd
#%% 
def thselect(x, tptr):
    x = np.array(x)
    l = len(x)

    if tptr == 'rigrsure':
        sx2 = [sx * sx for sx in np.absolute(x)]
        np.sort()
        cumsumsx2 = np.cumsum(sx2)
        risks = []
        for i in range(l):
            risks.append((l - 2 * (i + 1) + (cumsumsx2[i] + (l - 1 - i) * sx2[i])) / l)
        mini = np.argmin(risks)
        th = np.sqrt(sx2[mini])
    if tptr == 'heursure':
        hth = np.sqrt(2 * np.log(l))
        normsqr = np.dot(x, x)
        eta = 1.0 * (normsqr - l) / l
        crit = (np.log(l, 2) ** 1.5) / np.sqrt(l)
        if eta < crit:
            th = hth
        else:
            sx2 = [sx * sx for sx in np.absolute(x)]
            sx2.sort()
            cumsumsx2 = np.cumsum(sx2)
            risks = []
            for i in range(l):
                risks.append((l - 2 * (i + 1) + (cumsumsx2[i] + (l - 1 - i) * sx2[i])) / l)
            mini = np.argmin(risks)
            rth = np.sqrt(sx2[mini])
            th = min(hth, rth)
    elif tptr == 'sqtwolog':
        th = np.sqrt(2 * np.log(l))
    elif tptr == 'minimaxi':
        if l < 32:
            th = 0
        else:
            th = 0.3936 + 0.1829 * np.log(l, 2)
    else:
        raise ValueError('Invalid value, tptr = %s' % (tptr))

    return th
#%% 
def wthresh(x, sorh, t):
    if sorh == 'hard':
        y = [e * (abs(e) >= t) for e in x]
    elif sorh == 'soft':
        y = [((e < 0) * -1.0 + (e > 0)) * ((abs(e) - t) * (abs(e) >= t)) for e in x]
    else:
        raise ValueError('Invalid value, sorh = %s' % (sorh))

    return y
#%% 
def wnoisest(coeffs, level=None):
    l = len(coeffs) - 1

    if level == None:
        sig = [abs(s) for s in coeffs[-1]]
        stdc = median(sig) / 0.6745
    else:
        stdc = []
        for i in range(l):
            sig = [abs(s) for s in coeffs[1 + i]]
            stdc.append(median(sig) / 0.6745)

    return stdc
#%% 
def median(data):
    temp = data[:]
    temp.sort()
    dataLen = len(data)
    if dataLen % 2 == 0:
        med = (temp[int(dataLen / 2) - 1] + temp[int(dataLen / 2)]) / 2.0
    else:
        med = temp[int(dataLen / 2)]

    return med

#%% 
def lowpassfilter(signal, thresh = 0.63, wavelet="db4"):
    thresh = thresh*np.argmax(signal)
    coeff = pywt.wavedec(signal, wavelet, mode="per" )
    coeff[1:] = (pywt.threshold(i, value=thresh, mode="soft" ) for i in coeff[1:])
    reconstructed_signal = pywt.waverec(coeff, wavelet, mode="per" )
    return reconstructed_signal

# In[]:
if __name__ == '__main__':
    output_path = './Output'
    source_path = './Source\\testSignal.csv'
    s =  pd.read_csv(source_path, index_col=None,header =None)
    r1 = wden(s.values[:,0], 'sqtwolog', 'soft', 'mln', 3, 'db5')    
    r2 = lowpassfilter(s, thresh = 0.63, wavelet="db4")
