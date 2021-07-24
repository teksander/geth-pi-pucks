#!/usr/bin/env python3
# This is a scipt to anaylize data collected from groundsensors
# Assumptions:
# - Calibration datasets are in current directory
# - Calibration datasets are tittled <robotID>.csv
# Options:
# - If a flag is given then the data is plotted for each robot

import time
import os
import sys
import pandas as pd
from skimage.filters import threshold_otsu
from matplotlib import pyplot as plt
# from scipy.signal import find_peaks as peaks

rootdir = '/home/eksander/geth-pi-pucks/control/monitor-pc/calibration/'

for file in os.listdir(rootdir):
	if file.endswith(".csv"):
		df = pd.read_csv(rootdir+file, usecols=["S1", "S2", "S3"], delimiter=" ")
		thresh1 = threshold_otsu(df['S1'])
		thresh2 = threshold_otsu(df['S2'])
		thresh3 = threshold_otsu(df['S3'])
		
		with open(rootdir+file[0 : 3]+'-threshes.txt', 'w+') as calibFile:
			calibFile.write('{} {} {}'.format(thresh1, thresh2, thresh3))
			print(file[0 : 3],':', thresh1, thresh2, thresh3)

		# If a second argument (such as -v) is passed, show plots
		if len(sys.argv) == 2:

			fig, axs = plt.subplots(3)
			fig.suptitle('Robot '+file[0 : 3], fontsize=16)
			for ax in axs:
				ax.set_xlim([0,1100])
				# ax.set_ylim([0, 0.006])
			df['S1'].plot.hist(color='green', ax=axs[0], bins=100)
			df['S2'].plot.hist(color='red', ax=axs[1], bins=100)
			df['S3'].plot.hist(color='blue', ax=axs[2], bins=100)
			
			axs[0].axvline(thresh1, color='k')
			axs[1].axvline(thresh2, color='k')
			axs[2].axvline(thresh3, color='k')
			plt.show()

