#!/usr/bin/env python3
# This is a scipt to generate plots data collected from the robots
# Assumptions:
# - Robot datasets are in folder data/Experiment_<tittle>/<robotID>
# Options:
# - If a flag is given then the data is plotted for each robot

import time
import os
import sys
import pandas as pd
from matplotlib import pyplot as plt
import glob

global tstart

datadir = '/home/eksander/geth-pi-pucks/results/data'

def create_df_old(experiment, datafile):

    dd = dict()
    for repetition_folder in glob.glob('{}/Experiment_{}/*'.format(datadir, experiment)):

        data = list()
        for robot_file in glob.glob('{}/*/{}.csv'.format(repetition_folder, datafile)):
#             print(robot_file)
            newdf = pd.read_csv(robot_file, delimiter=" ")
            data.append(perform_corrections(newdf))

        dd[repetition_folder.split('/')[-1]] = pd.concat(data, ignore_index=True)

        dd_allreps = pd.concat(list(dd.values()), ignore_index=True)

    return dd, dd_allreps

def perform_corrections(df):
    df['TIME'] = (1000*df['TIME']).astype(int)
    try:
        df['ESTIMATE'] = pd.to_numeric(df['ESTIMATE'], errors='coerce')
    except KeyError:
        pass

    return df
        
# This function should yield per robot DFs, per experiment DFs, or all if the person requests
def create_dfV2(experiment, datafile):

    rep_df_dict = dict()
    for repetition_folder in glob.glob('{}/Experiment_{}/*'.format(datadir, experiment)):
        
        rob_df_dict = dict()                
        for robot_file in glob.glob('{}/*/{}.csv'.format(repetition_folder, datafile)):
            df = pd.read_csv(robot_file, delimiter=" ")
            df = perform_corrections(df)
            rob_df_dict[robot_file.split('/')[-2]] = df
            
            
        rep_df_dict[repetition_folder.split('/')[-1]] = rob_df_dict
        
        
    return rep_df_dict

def create_df(experiment, datafile):

    data_list = []
    for rep_folder in glob.glob('{}/Experiment_{}/*'.format(datadir, experiment)):
        rep = rep_folder.split('/')[-1]
        
        for rob_file in glob.glob('{}/*/{}.csv'.format(rep_folder, datafile)):
            rob = rob_file.split('/')[-2]
            
            df = pd.read_csv(rob_file, delimiter=" ")
            df['NREP'] = int(rep.split('-')[-1])
            df['NBYZ'] = int(rep.split('-')[-2][:-3])
            df['NROB'] = int(rep.split('-')[-3][:-3])
            df = perform_corrections(df)
            data_list.append(df)
            
    full_df = pd.concat(data_list, ignore_index=True)
    return full_df

def tic():
    global tstart
    tstart = time.time()
    
def toc():
    print(time.time()-tstart)