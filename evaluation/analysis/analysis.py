# written by clare lohrmann

from scipy.stats import shapiro 
from scipy.stats import ttest_ind, mannwhitneyu
import numpy as np
from scipy.stats import f_oneway
from scipy import stats

import math
import base64

import matplotlib.pyplot as plt
from matplotlib.container import BarContainer

group1_color = '#446F24'
group2_color = '#DFE4B0'

group1_name = ""
group2_name = ""

def get_dists(cols, group1, group2,info=False):
    normal_d = []
    
    #for each piece, check distribution
    cleaned = []
    for t in cols:
        if info: print(t)
        if len(group1[t]) >= 3 and len(group2[t]) >= 3:
            normal_d.append((shapiro(group1[t]).pvalue > 0.05, shapiro(group2[t]).pvalue > 0.05))
            cleaned.append(t)
        else:
            if info: print(t, 'Insufficient data for distribution at this time!')
                
    return normal_d, cleaned

def get_variances(cols, group1, group2):
    variances = []
    
    #for each piece, check variance
    for t in cols:
        if group1[t].var() == group2[t].var():
            variances.append("eq")
        else:
            variances.append("no")
            
    return variances
            
def pick_test(varis,dists):
    if varis == "eq" and dists == (True,True):
        return "t-test"
    elif varis != "eq" and dists == (True,True):
        return "t-test false"
    else:
        return "Kruskal-Wallis"
    
def get_res(test,col1,col2):
    if 't-test' in test:
        if 'false' in test:
            res = ttest_ind(a=col1, b=col2, equal_var=False)
        else:
            res = ttest_ind(a=col1, b=col2, equal_var=True)
            
    else:
        res = stats.kruskal(col1, col2)
        
    return res
    
def print_results(pvalue,t,g1Mean,g2Mean,test,info=False):
    if pvalue < 0.05:
        print(t)
        print("Significant",pvalue)
        print('Group 1 mean:',g1Mean, 'Group 2 mean:',g2Mean)
        if info: print('Tested used: '+ test.split(" ")[0])
        print('*****************')
    else:
        if info: 
            print(t)
            print("Not Significant",pvalue)
            print('Group 1 mean:',g1Mean, 'Group 2 mean:',g2Mean)
            print('*****************')
        

def analyze(df, target_cols, info=False):
    group1 = df[df['group'] == group1_name]
    group2 = df[df['group'] == group2_name]
    
    normal_dists, cleaned_target_cols = get_dists(target_cols, group1, group2, info=info)  
        
    if info: print('Distributions checked')
        
    variances = get_variances(cleaned_target_cols, group1, group2)
            
    if info: print('Variances checked')
        
    #run appropriate test
    for i,t in enumerate(cleaned_target_cols):
        if info: print(variances, normal_dists)
        test = pick_test(variances[i],normal_dists[i])
        
        res = get_res(test,group1[t],group2[t])
        
        print_results(res.pvalue,t,group1[t].mean(),group2[t].mean(),test,info=info)
        
def barplot_annotate_brackets(num1, num2, data, center, height, yerr=None, dh=.05, barh=.05, fs=None, maxasterix=None,staroverride=False):
    """ 
    Annotate barplot with p-values.

    :param num1: number of left bar to put bracket over
    :param num2: number of right bar to put bracket over
    :param data: string to write or number for generating asterixes
    :param center: centers of all bars (like plt.bar() input)
    :param height: heights of all bars (like plt.bar() input)
    :param yerr: yerrs of all bars (like plt.bar() input)
    :param dh: height offset over bar / bar + yerr in axes coordinates (0 to 1)
    :param barh: bar height in axes coordinates (0 to 1)
    :param fs: font size
    :param maxasterix: maximum number of asterixes to write (for very small p-values)
    """

    if type(data) is str:
        text = data
    else:
        # * is p < 0.05
        # ** is p < 0.005
        # *** is p < 0.0005
        # etc.
        text = ''
        p = .05

        while data < p:
            text += '*'
            p /= 10.

            if maxasterix and len(text) == maxasterix:
                break

        if len(text) == 0:
            text = 'n. s.'
        elif staroverride:
            text = 'p < 0.' + '0'*len(text) + '5'

    lx, ly = center[num1], height[num1]
    rx, ry = center[num2], height[num2]

    if yerr:
        ly += yerr[num1]
        ry += yerr[num2]

    ax_y0, ax_y1 = plt.gca().get_ylim()
    dh *= (ax_y1 - ax_y0)
    barh *= (ax_y1 - ax_y0)

    y = max(ly, ry) + dh

    barx = [lx, lx, rx, rx]
    bary = [y, y+barh, y+barh, y]
    mid = ((lx+rx)/2, y+barh+0.3)

    plt.plot(barx, bary, c='black')

    kwargs = dict(ha='center', va='bottom')
    if fs is not None:
        kwargs['fontsize'] = fs

    plt.text(*mid, text, **kwargs)
    
def find_all(a_str, sub):
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1: return
        yield start
        start += len(sub) # use start += 1 to find overlapping matches

def insert_newlines(string, every=64):
    spaces = list(find_all(string," "))
    everys = list(range(0, len(string), every))
    best = [min(spaces, key=lambda x:abs(x-e)) for e in everys]
    lines = [string[0:best[0]]]
    for i, b in enumerate(best[:-1]):
        lines.append(string[b:best[i+1]])
        
    lines.append(string[best[-1]:])
    return '\n'.join(lines)
        
def visualize(title, questions, group_means, pvals, longLabels=-1,save=False,ylabel="",xlabel=""):
    if longLabels != -1:
        questions = [insert_newlines(q,every=longLabels) for q in questions]
        
    print(questions)
        
    # create data 
    x = np.arange(len(questions)) 
    y1 = list(group_means[group1_name])
    y2 = list(group_means[group2_name]) 
    width = 0.40

    max_ylim = int(max([item for t in group_means.values() for item in t]) * 1.5)

    fig = plt.figure()
    ax = fig.add_axes([0.1, 0.1, 0.8, 0.8]) # main axes

    # plot data in grouped manner of bar type 
    ax.bar(x-0.2, y1, width, label=group1_name,color=[group1_color]*len(y1)) 
    ax.bar(x+0.2, y2, width, label=group2_name,color=[group2_color]*len(y2)) 

    ax.set_xticks(x, questions)
    ax.legend(loc='upper left', ncols=2)
    ax.set_ylim(0, max_ylim)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)

    bars = [i for i in ax.containers if isinstance(i, BarContainer)]

    heights = [item for t in [b.datavalues for b in bars] for item in t]
    centers = np.concatenate((x-0.2,x+0.2))

    for i, p in enumerate(pvals):
        if p < 0.05: #add a bar
            barplot_annotate_brackets(i, i+len(questions), p, centers, heights)
            
    if save:
        fig.savefig(title+".svg",bbox_inches='tight')
        
def visualize_box(title, questions, datas, pvals, longLabels=-1,save=False,ylabel="",xlabel="",staroverride=False):
        
    # create data 
    x = np.arange(len(questions)) 
    ys = []
    
    for q in list(datas.keys()):
        y_tmp = []
        y_tmp.append(datas[q][group1_name])
        y_tmp.append(datas[q][group2_name])
        
        ys.append(y_tmp)
    
    if longLabels != -1:
        questions = [insert_newlines(q,every=longLabels) for q in questions]

    max_ylim = int(max([max(max(y[0]),max(y[1])) for y in ys]) * 1.3)
    
    print(max_ylim)

    labels = [group1_name, group2_name]
    colors = [group1_color,group2_color]

    fig, ax = plt.subplots()
    
    #ax.legend(loc='upper left', ncols=2)
    #ax.set_ylim(0, max_ylim)
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    
    pos = 1
    
    ticks = []
    heights1 = []
    heights2 = []
    
    boxes = []
    
    for y_set in ys:
        bplot = ax.boxplot(y_set, positions = [pos, pos + 1], widths = 0.6,patch_artist=True,showfliers=False)
        ticks.append(pos+0.5)
        pos += 3
        
        #print([b.get_ydata() for b in bplot['whiskers']])
        
        heights1.append(bplot['whiskers'][1].get_ydata()[1])
        heights2.append(bplot['whiskers'][3].get_ydata()[1])
        
        for patch, color in zip(bplot['boxes'], colors):
            patch.set_facecolor(color)
            boxes.append(patch)

    ax.set_xticks(ticks)
    ax.set_xticklabels(questions)
    ax.legend(boxes, labels)
     
    heights = heights1 + heights2    
    heights = [h + 0.2 for h in heights]
    #print(heights)
    
    max_ylim = int(max(heights) * 1.3)#int(max([max(max(y[0]),max(y[1])) for y in ys]) * 1.3)
    
    print(max_ylim)
    
    ax.set_ylim(0, max_ylim)

    centers = []
    for t in ticks:
        centers.append(t-0.6)
    for t in ticks:
        centers.append(t+0.6)

    for i, p in enumerate(pvals):
        if p < 0.05: #add a bar
            #print(heights[i],heights[i+len(questions)])
            barplot_annotate_brackets(i, i+len(questions), p, centers, heights,staroverride=staroverride,fs=8)
            
    if save:
        fig.savefig(title+"_box.svg",bbox_inches='tight')
        
def visualize_box_simple(title, questions, datas, pvals, longLabels=-1,save=False,ylabel="",xlabel="",staroverride=False):
        
    # create data 
    x = np.arange(len(questions)) 
    ys = []
    
    for q in list(datas.keys()):
        y_tmp = []
        y_tmp.append(datas[q][group1_name])
        y_tmp.append(datas[q][group2_name])
        
        ys.append(y_tmp)
    
    if longLabels != -1:
        questions = [insert_newlines(q,every=longLabels) for q in questions]

    labels = [group1_name, group2_name]
    colors = [group1_color,group2_color]

    fig, ax = plt.subplots()
    
    #ax.legend(loc='upper left', ncols=2)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    
    pos = 1
    
    ticks = []
    heights1 = []
    heights2 = []
    
    for y_set in ys:
        bplot = ax.boxplot(y_set, positions = [pos, pos + 1], widths = 0.6,patch_artist=True,showfliers=False)
        ticks.append(pos)
        ticks.append(pos+1)
        pos += 3
        
        #print([b.get_ydata() for b in bplot['whiskers']])
        
        heights1.append(bplot['whiskers'][1].get_ydata()[1])
        heights2.append(bplot['whiskers'][3].get_ydata()[1])
        
        for patch, color in zip(bplot['boxes'], colors):
            patch.set_facecolor(color)

    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
     
    heights = heights1 + heights2    
    heights = [h + 0.2 for h in heights]
    #print(heights)
    
    max_ylim = int(max(heights) * 1.3)#int(max([max(max(y[0]),max(y[1])) for y in ys]) * 1.3)
    
    print(max_ylim)
    
    ax.set_ylim(0, max_ylim)

    centers = []
    for t in ticks:
        centers.append(t-0.1)
    for t in ticks:
        centers.append(t+1.1)

    for i, p in enumerate(pvals):
        if p < 0.05: #add a bar
            #print(heights[i],heights[i+len(questions)])
            barplot_annotate_brackets(i, i+len(questions), p, centers, heights,staroverride,fs=8)
            
    if save:
        fig.savefig(title+"_box.svg",bbox_inches='tight')