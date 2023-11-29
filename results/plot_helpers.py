#!/usr/bin/env python3
# This is a scipt to generate plots data collected from the robots
# Assumptions:
# - Robot datasets are in folder data/Experiment_<tittle>/<robotID>
# Options:
# - If a flag is given then the data is plotted for each robot

import time
import os
import sys
import subprocess
import pandas as pd
from matplotlib import pyplot as plt
import glob
from graphviz import Digraph
import pydotplus
import networkx as nx
from networkx.algorithms.shortest_paths.generic import shortest_path as get_mainchain

global tstart

datadir = '/home/eksander/geth-pi-pucks/results/data'
plotdir = '/home/eksander/geth-pi-pucks/results/plots/'

def tic():
    global tstart
    tstart = time.time()
def toc():
    print(time.time()-tstart)  

def create_df(experiments, logfile, exclude_patterns = []):
    df_list = []
    experiments = [experiments] if isinstance(experiments, str) else experiments
    
    for experiment in experiments:
        
        # Make sure data and plot folder exists
        exp_plotdir = '%s/%s' % (plotdir, experiment)
        exp_datadir = '%s/%s' % (datadir, experiment)
        
        if not os.path.exists(exp_datadir):
            print("Dataset %s not found" % exp_datadir)
            continue
        
        if not os.path.exists(exp_plotdir):
          os.makedirs(exp_plotdir)
          print("New plot directory is created!")
        
        configs = sorted(glob.glob('%s/%s/*/' % (datadir, experiment)))

        if exclude_patterns:
            for exclude in exclude_patterns:
                configs = [config for config in configs if exclude not in config]

        for config in configs:
            csvfile_list = sorted(glob.glob('%s/*/*/%s.csv' % (config, logfile)))
            
            for csvfile in csvfile_list:
                df = pd.read_csv(csvfile, delim_whitespace=True)
                df['EXP'] = experiment 
                df['CFG'] = config.split('/')[-2]
                df['REP'] = csvfile.split('/')[-3]
                df = perform_corrections(df)
                df_list.append(df)
        
    if df_list:
        full_df = pd.concat(df_list, ignore_index=True)
        full_df.get_param = get_param_df
        return full_df
    else:
        return None

def get_param_df(df, param_dict, param, alias = None):
    df = df.groupby(['EXP','CFG','REP']).apply(lambda x: get_param(x, x.name , param_dict, param, alias))
    return df

def get_param(group, name, param_dict, param, alias):
    exp = name[0]
    cfg = name[1]
    rep = name[2]
    
    configfile = '%s/%s/%s/%s/config.py' % (datadir, exp, cfg, rep)
    exec(open(configfile).read(), globals())
    param_dict = eval(param_dict)
    if param in param_dict:
        if alias:
            group[alias] = repr(param_dict[param])
        else:
            group[param] = param_dict[param]
    return group

def get_config_dicts(exp,cfg,rep):
    configfile = '%s/%s/%s/%s/config.py' % (datadir, exp, cfg, rep)
#     print(open(configfile).read())
    with open(configfile) as f:
        for line in f:
            print(line)

    
def perform_corrections(df):

    if 'DIST' in df.columns:
        df['DIST'] = df['DIST']/100
        
    if 'RECRUIT_DIST' in df.columns:
        df['RECRUIT_DIST'] = df['RECRUIT_DIST']/100
        
    if 'SCOUT_DIST' in df.columns:
        df['SCOUT_DIST'] = df['SCOUT_DIST']/100
        
    if 'MB' in df.columns:
        df['MB'] = df['MB']*10e-6
            
    return df


# Construct digraph
def create_digraph(df):
    # Default settings for blockchain viz
    digraph = Digraph(comment='Blockchain', 
                      edge_attr={'arrowhead':'none'},
                      node_attr={'shape': 'record', 'margin': '0', 'fontsize':'9', 'height':'0.35', 'width':'0.35'}, 
                      graph_attr={'rankdir': 'LR', 'ranksep': '0.1', 'splines':'ortho'})
    

#     df.apply(lambda row : digraph.node(row['HASH'], str(row['BLOCK'])), axis = 1)
    digraph.node(df['PHASH'].iloc[0], '<f0> {} | <f1> {}'.format(df['PHASH'].iloc[0][2:6], 'Genesis'))
    df.apply(lambda row : digraph.node(row['HASH'], '<f0> {} | <f1> {}'.format(row['HASH'][2:6], str(row['BLOCK']))), axis = 1)
    df.apply(lambda row : digraph.edge(row['PHASH'], row['HASH']), axis = 1)
    
    return digraph

def get_mainchain_df2(df, leaf):
    mainchain = [leaf]
    main_path = []
    
    for (idx, row) in df[::-1].iterrows():
        if row['PHASH'] in main_path:
            main_path.append(idx)
        
    return df.iloc[main_path]


def get_mainchain_df(df, leaf):
    parentHash = leaf
    main_list  = [parentHash]
    main_path = []
    
    for (idx, row) in df[::-1].iterrows():
        if row['HASH'] == parentHash:
            main_path.append(idx)
            main_list.append(row['PHASH'])
            parentHash = row['PHASH']
        
    return df.iloc[main_path]


def convert_digraph(digraph):
    return nx.nx_pydot.from_pydot(pydotplus.graph_from_dot_data(digraph.source))

# Remove childless blocks
def trim_chain(df, levels=1):
    sub_df = df
    while levels:
        sub_df = sub_df.query('HASH in PHASH')
        levels -= 1
    return sub_df

def paths_longer_than(paths, n):
    return [x for x in paths if len(x)>=n]

def nodes_in_paths(paths):
    return [item for sublist in paths for item in sublist]

###########################################################################
from scipy.optimize import curve_fit
def LinearRegression0(group, x, y):
    # objective function
    def model(x, a):
        return a * x
    coefs, _ = curve_fit(model, group[x], group[y])
    a = float(coefs)
    group['COEFS'] = a
    group['LREG'] = model(group[x], a)
    return group

def LinearRegression(group, x, y):
    # objective function
    def model(x, a, b):
        return a * x + b
    coefs, _ = curve_fit(model, group[x], group[y])
#     a = float(coefs)
    group['COEFS'] = repr(coefs)
    group['LREG'] = model(group[x], *coefs)
    return group

import colorsys
def bgr_to_hsv_csys(bgr):
    h,s,v = colorsys.rgb_to_hsv(*bgr[::-1])
    return (h*180, s*255, v)

import cv2
import numpy as np
def bgr_to_hsv_cv2(bgr):
    h,s,v = cv2.cvtColor(np.array(bgr, dtype=np.uint8).reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0][0]
    return h,s,v

######## Random stuff
def bgr_to_hsv(b, g, r):
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0
    
    cmax = max(r_norm, g_norm, b_norm)
    cmin = min(r_norm, g_norm, b_norm)
    delta = cmax - cmin
    
    # Calculate hue
    if delta == 0:
        h = 0
    elif cmax == r_norm:
        h = 60 * (((g_norm - b_norm) / delta) % 6)
    elif cmax == g_norm:
        h = 60 * (((b_norm - r_norm) / delta) + 2)
    elif cmax == b_norm:
        h = 60 * (((r_norm - g_norm) / delta) + 4)
    
    # Calculate saturation
    if cmax == 0:
        s = 0
    else:
        s = delta / cmax
    
    # Calculate value
    v = cmax
    
    return h, s, v
import math
def colourBGRDistance(p1, p2):
    space_size = len(p1)
    divisor = 100000
    rp1 = [0] * space_size
    rp2 = [0] * space_size

    for i in range(space_size):
        rounded = p1[i] // divisor

        if rounded < 0:
            rounded = 0
        rp1[i] = rounded

        rounded = p2[i] // divisor
        if rounded < 0:
            rounded = 0
        rp2[i] = rounded

    rMean = (rp1[2] + rp2[2]) // 2
    r = rp1[2] - rp2[2]
    g = rp1[1] - rp2[1]
    b = rp1[0] - rp2[0]
    distance = ((((512 + rMean) * r * r) >> 8) + 4 * g * g + (((767 - rMean) * b * b) >> 8))
    distance = math.sqrt(distance) * 100000
    return distance

def manhattan_distance(p1, p2):
    """
    Compute the Manhattan distance between two points.
    
    Arguments:
    p1, p2 -- Tuples or lists representing the coordinates of the two points.
    
    Returns:
    The Manhattan distance between the two points.
    """
    if len(p1) != len(p2):
        raise ValueError("Both points should have the same number of coordinates.")
    
    distance = 0
    for i in range(len(p1)):
        distance += abs(p1[i] - p2[i])
    
    return distance

def chebyshev_distance(point1, point2):
    """
    Compute the Chebyshev distance between two points.
    
    Arguments:
    point1, point2 -- Tuples or lists representing the coordinates of the two points.
    
    Returns:
    The Chebyshev distance between the two points.
    """
    if len(point1) != len(point2):
        raise ValueError("Both points should have the same number of coordinates.")
    
    distance = 0
    for i in range(len(point1)):
        distance = max(distance, abs(point1[i] - point2[i]))
    
    return distance