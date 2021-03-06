#!/usr/bin/python3
import math

import dpkt, datetime, glob, os, csv
import socket
from pathlib import Path

import matplotlib
from PIL import Image
from matplotlib.pyplot import cm
from collections import deque

from sklearn import metrics
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from sklearn.manifold import TSNE
import seaborn as sns
import hdbscan
import time

from graphviz import render

from src.util.numba_cosine import cosine_similarity_numba
from src.util.odtw import _dtw_distance


class MalpacaMeImprovedWindow():
    expname = 'exp'
    window_size = 20
    RPY2 = False
    totalconn = 0

    def __init__(self, path_to_folder, path_to_results, expname, window_size, RPY2):
        self.path_to_folder = path_to_folder
        self.expname = expname
        self.window_size = window_size
        self.RPY2 = RPY2

        path_to_results = path_to_results
        os.mkdir(path_to_results + "/" + expname)
        self.path_to_store = str(Path.joinpath(Path(path_to_results), expname)) + "/"

        self.readfolde_window()

        if RPY2 == True:
            pass

    def difference(self, str1, str2):
        return sum([str1[x] != str2[x] for x in range(len(str1))])

    # @profile
    def connlevel_sequence(self, metadata, mapping):
        inv_mapping = {v: k for k, v in mapping.items()}
        data = metadata
        timing = {}

        values = list(data.values())
        keys = list(data.keys())
        distm = []
        labels = []
        ipmapping = []

        # save intermediate results

        path_to_intermediate_results = self.path_to_store + "/intermediate_results/"
        os.mkdir(path_to_intermediate_results)

        path_to_features = path_to_intermediate_results  +"/features/"
        os.mkdir(path_to_features)

        path_to_distances = path_to_intermediate_results  +"/distances/"
        os.mkdir(path_to_distances)


        addition = '_' + self.expname + '_' + str(self.window_size)

        # ----- start porting -------

        utils, r = None, None

        for n, feat in [(1, 'bytes'), (0, 'gaps'), (3, 'sport'), (4, 'dport')]:
            f = open(path_to_features + feat + '-features' + addition + '.txt', 'w')
            for val in values:
                vi = [str(x[n]) for x in val]
                f.write(','.join(vi))
                f.write("\n")
            f.close()

        startb = time.time()
        start_time = time.time()

        filename = path_to_distances + 'bytesDist' + addition + '.txt'

        print("Starting bytes dist")

        distm = [-1] * len(data.values())
        distm = [[-1] * len(data.values()) for i in distm]

        for a in range(len(data.values())):  # range(10):

            labels.append(mapping[keys[a]])
            ipmapping.append((mapping[keys[a]], inv_mapping[mapping[keys[a]]]))
            for b in range(a + 1):

                i = [x[1] for x in values[a]][:self.window_size]
                j = [x[1] for x in values[b]][:self.window_size]
                if len(i) == 0 or len(j) == 0: continue

                if a == b:
                    distm[a][b] = 0.0
                else:
                    first_array = np.array(i)
                    second_array = np.array(j)

                    dist = _dtw_distance(first_array, second_array)
                    distm[a][b] = dist
                    distm[b][a] = dist

        with open(filename, 'w') as outfile:
            for a in range(len(distm)):  # len(data.values())): #range(10):
                outfile.write(' '.join([str(e) for e in distm[a]]) + "\n")
        outfile.close()
        with open(path_to_intermediate_results + 'labels' + addition + '.txt', 'w') as outfile:
            outfile.write(' '.join([str(l) for l in labels]) + '\n')
        outfile.close()
        with open(path_to_intermediate_results + 'mapping' + addition + '.txt', 'w') as outfile:
            outfile.write(' '.join([str(l) for l in ipmapping]) + '\n')
        outfile.close()

        endb = time.time()
        print('Time bytes: ' + str(round((endb - startb), 3)))
        ndistmB = []
        mini = min(min(distm))
        maxi = max(max(distm))

        for a in range(len(distm)):
            ndistmB.append([])
            for b in range(len(distm)):
                normed = (distm[a][b] - mini) / (maxi - mini)
                ndistmB[a].append(normed)

        startg = time.time()
        distm = []

        filename = path_to_distances + 'gapsDist' + addition + '.txt'

        print("Starting gaps dist")
        distm = [-1] * len(data.values())
        distm = [[-1] * len(data.values()) for i in distm]

        for a in range(len(data.values())):  # range(10):

            for b in range(a + 1):

                i = [x[0] for x in values[a]][:self.window_size]
                j = [x[0] for x in values[b]][:self.window_size]

                if len(i) == 0 or len(j) == 0: continue

                if a == b:
                    distm[a][b] = 0.0
                else:
                    first_array = np.array(i)
                    second_array = np.array(j)

                    dist = _dtw_distance(first_array, second_array)
                    distm[a][b] = dist
                    distm[b][a] = dist

        with open(filename, 'w') as outfile:
            for a in range(len(distm)):  # len(data.values())): #range(10):
                # print distm[a]
                outfile.write(' '.join([str(e) for e in distm[a]]) + "\n")

        endg = time.time()
        print('Time gaps: ' + str(round((endg - startg), 3)))
        ndistmG = []
        mini = min(min(distm))
        maxi = max(max(distm))

        for a in range(len(distm)):  # len(data.values())): #range(10):
            ndistmG.append([])
            for b in range(len(distm)):
                normed = (distm[a][b] - mini) / (maxi - mini)
                ndistmG[a].append(normed)

        # source port
        ndistmS = []
        distm = []

        starts = time.time()

        filename = path_to_distances + 'sportDist' + addition + '.txt'
        same, diff = set(), set()

        print("Starting sport dist")
        distm = [-1] * len(data.values())
        distm = [[-1] * len(data.values()) for i in distm]

        ngrams = []
        for a in range(len(values)):
            profile = dict()

            dat = [x[3] for x in values[a]][:self.window_size]

            li = zip(dat, dat[1:], dat[2:])
            for b in li:
                if b not in profile.keys():
                    profile[b] = 0

                profile[b] += 1

            ngrams.append(profile)

        profiles = []
        # update for arrays

        assert len(ngrams) == len(values)
        for a in range(len(ngrams)):
            for b in range(a + 1):
                if a == b:
                    distm[a][b] = 0.0
                else:
                    i = ngrams[a]
                    j = ngrams[b]
                    ngram_all = list(set(i.keys()) | set(j.keys()))
                    i_vec = [(i[item] if item in i.keys() else 0) for item in ngram_all]
                    j_vec = [(j[item] if item in j.keys() else 0) for item in ngram_all]
                    #dist = cosine(i_vec, j_vec)

                    first_array = np.array(i_vec)
                    second_array = np.array(j_vec)

                    dist = round(cosine_similarity_numba(first_array, second_array), 8)

                    distm[a][b] = dist
                    distm[b][a] = dist

        with open(filename, 'w') as outfile:
            for a in range(len(distm)):
                outfile.write(' '.join([str(e) for e in distm[a]]) + "\n")

        ends = time.time()
        print('Sport time: ' + str(round((ends - starts), 3)))


        for a in range(len(distm)):
            ndistmS.append([])
            for b in range(len(distm)):
                ndistmS[a].append(distm[a][b])

        # dest port
        ndistmD = []
        distm = []

        startd = time.time()

        filename = path_to_distances + 'dportDist' + addition + '.txt'

        print("Starting dport dist")
        distm = [-1] * len(data.values())
        distm = [[-1] * len(data.values()) for i in distm]

        ngrams = []
        for a in range(len(values)):

            profile = dict()
            dat = [x[4] for x in values[a]][:self.window_size]

            li = zip(dat, dat[1:], dat[2:])

            for b in li:
                if b not in profile.keys():
                    profile[b] = 0
                profile[b] += 1
            ngrams.append(profile)

        assert len(ngrams) == len(values)
        for a in range(len(ngrams)):
            for b in range(a + 1):
                if a == b:
                    distm[a][b] = 0.0
                else:
                    i = ngrams[a]
                    j = ngrams[b]
                    ngram_all = list(set(i.keys()) | set(j.keys()))
                    i_vec = [(i[item] if item in i.keys() else 0) for item in ngram_all]
                    j_vec = [(j[item] if item in j.keys() else 0) for item in ngram_all]
                    #dist = round(cosine(i_vec, j_vec), 8)

                    first_array = np.array(i_vec)
                    second_array = np.array(j_vec)

                    dist = round(cosine_similarity_numba(first_array, second_array), 8)

                    distm[a][b] = dist
                    distm[b][a] = dist

        with open(filename, 'w') as outfile:
            for a in range(len(distm)):
                outfile.write(' '.join([str(e) for e in distm[a]]) + "\n")

        endd = time.time()
        print('Time dport: ' + str(round((endd - startd), 3)))
        mini = min(min(distm))
        maxi = max(max(distm))

        for a in range(len(distm)):
            ndistmD.append([])
            for b in range(len(distm)):
                ndistmD[a].append(distm[a][b])

        ndistm = []

        for a in range(len(ndistmS)):
            ndistm.append([])
            for b in range(len(ndistmS)):
                ndistm[a].append((ndistmB[a][b] + ndistmG[a][b] + ndistmD[a][b] + ndistmS[a][b]) / 4.0)

        print("Done with distance measurement")
        print("----------------")

        plot_kwds = {'alpha': 0.5, 's': 80, 'linewidths': 0}
        RS = 3072018
        projection = TSNE(random_state=RS).fit_transform(ndistm)
        plt.scatter(*projection.T)
        plt.savefig(self.path_to_store + "tsne-result" + addition)

        plt.close()
        plt.clf()

        #########
        # Model #
        #########

        path_to_model = path_to_intermediate_results +"/model/"
        os.mkdir(path_to_model)

        size = 7
        sample = 7

        model = hdbscan.HDBSCAN(min_cluster_size=size, min_samples=sample, cluster_selection_method='leaf',
                                metric='precomputed')
        clu = model.fit(np.array([np.array(x) for x in ndistm]))  # final for citadel and dridex

        input_array = np.array([np.array(x) for x in ndistm])
        validity_index = hdbscan.validity_index(X=input_array, labels=clu.labels_, metric='precomputed', d=4)

        unique_labels = np.unique(np.array(clu.labels_))
        if (len(unique_labels) >= 2):
            silhouette_score = round(metrics.silhouette_score(X=input_array, labels=np.array(clu.labels_), metric='precomputed'), 3)
        else:
            silhouette_score = "nan"

        joblib.dump(clu, path_to_model + 'model' + addition + '.pkl')

        print("Num clusters: " + str(len(set(clu.labels_)) - 1))

        end_time = time.time()

        avg = 0.0
        for l in list(set(clu.labels_)):
            if l != -1:
                avg += sum([(1 if x == l else 0) for x in clu.labels_])
        #print("average size of cluster:" + str(float(avg) / float(len(set(clu.labels_)) - 1)))
        print("Samples in noise: " + str(sum([(1 if x == -1 else 0) for x in clu.labels_])))

        cols = ['royalblue', 'red', 'darksalmon', 'sienna', 'mediumpurple', 'palevioletred', 'plum', 'darkgreen',
                'lightseagreen', 'mediumvioletred', 'gold', 'navy', 'sandybrown', 'darkorchid', 'olivedrab', 'rosybrown',
                'maroon', 'deepskyblue', 'silver']
        pal = sns.color_palette(cols)  #

        extra_cols = len(set(clu.labels_)) - 18

        pal_extra = sns.color_palette('Paired', extra_cols)
        pal.extend(pal_extra)
        col = [pal[x] for x in clu.labels_]
        assert len(clu.labels_) == len(ndistm)

        mem_col = [sns.desaturate(x, p) for x, p in zip(col, clu.probabilities_)]

        plt.scatter(*projection.T, s=50, linewidth=0, c=col, alpha=0.2)

        for i, txt in enumerate(clu.labels_):

            realind = labels[i]
            name = inv_mapping[realind]
            plt.scatter(projection.T[0][i], projection.T[1][i], color=col[i], alpha=0.6)
            if txt == -1:
                continue

            plt.annotate(txt, (projection.T[0][i], projection.T[1][i]), color=col[i], alpha=0.6)

        plt.savefig(self.path_to_store + "clustering-result" + addition)
        plt.close()
        plt.clf()

        print("----------------")

        # writing csv file
        print("Writing csv file")
        final_clusters = {}
        final_probs = {}
        for lab in set(clu.labels_):
            occ = [i for i, x in enumerate(clu.labels_) if x == lab]
            final_probs[lab] = [x for i, x in zip(clu.labels_, clu.probabilities_) if i == lab]
            print("cluster: " + str(lab) + " num items: " + str(len([labels[x] for x in occ])))
            final_clusters[lab] = [labels[x] for x in occ]

        csv_file = self.path_to_store + 'summary' + addition + '.csv'
        outfile = open(csv_file, 'w')
        outfile.write("clusnum,connnum,probability,filename,src_ip,dst_ip,window\n")

        for n, clus in final_clusters.items():

            for idx, el in enumerate([inv_mapping[x] for x in clus]):

                ip = el.split('->')

                filename = ip[0]
                src_ip = ip[1]
                dst_ip = ip[2]
                window = ip[3]

                outfile.write(
                    str(n) + "," + str(mapping[el]) + "," + str(final_probs[n][idx])  + "," + str(filename) + "," + src_ip + "," + dst_ip + "," + window + "\n")
        outfile.close()

        other_csv_files = glob.glob(self.path_to_folder + "/*.csv")

        for index, csv_file_path in enumerate(other_csv_files):

            temp_df = pd.read_csv(csv_file_path)

            if index == 0:
                combined_df = temp_df
            else:
                combined_df = combined_df.append(temp_df)


        csv_df = pd.read_csv(csv_file)
        csv_df = csv_df.sort_values(by=['src_ip', 'dst_ip'])
        combined_df = combined_df.sort_values(by=['src_ip', 'dst_ip'])

        print(len(combined_df.index))
        print(len(csv_df.index))
        csv_df = csv_df.merge(right=combined_df, on=['src_ip', 'dst_ip', 'window'], how="left")

        csv_df = csv_df.drop(columns="filename")
        csv_df = csv_df.sort_values(by="clusnum")
        csv_df.to_csv(csv_file, index=False)

        # Making tree
        print('Producing DAG with relationships between pcaps')
        clusters = {}
        numclus = len(set(clu.labels_))
        with open(csv_file, 'r') as f1:
            reader = csv.reader(f1, delimiter=',')
            for i, line in enumerate(reader):  # f1.readlines()[1:]:
                if i > 0:
                    if line[4] not in clusters.keys():
                        clusters[line[4]] = []
                    clusters[line[4]].append((line[3], line[0]))  # classname, cluster#
        # print(clusters)
        f1.close()
        array = [str(x) for x in range(numclus - 1)]
        array.append("-1")

        treeprep = dict()
        for filename, val in clusters.items():
            arr = [0] * numclus
            for fam, clus in val:
                ind = array.index(clus)
                arr[ind] = 1
            # print(filename, )
            mas = ''.join([str(x) for x in arr[:-1]])
            famname = fam
            if mas not in treeprep.keys():
                treeprep[mas] = dict()
            if famname not in treeprep[mas].keys():
                treeprep[mas][famname] = set()
            treeprep[mas][famname].add(str(filename))

        os.mkdir(Path.joinpath(Path(self.path_to_store), "dag"))
        path_to_dag_results = str(Path.joinpath(Path(self.path_to_store), "dag")) + "/"

        f2 = open(path_to_dag_results +'mas-details' + addition + '.csv', 'w')
        for k, v in treeprep.items():
            for kv, vv in v.items():
                f2.write(str(k) + ';' + str(kv) + ';' + str(len(vv)) + '\n')
        f2.close()

        with open(path_to_dag_results +'mas-details' + addition + '.csv', 'rU') as f3:
            csv_reader = csv.reader(f3, delimiter=';')

            graph = {}

            names = {}
            for line in csv_reader:
                graph[line[0]] = set()
                if line[0] not in names.keys():
                    names[line[0]] = []
                names[line[0]].append(line[1] + "(" + line[2] + ")")

            zeros = ''.join(['0'] * (numclus - 1))
            if zeros not in graph.keys():
                graph[zeros] = set()

            ulist = graph.keys()
            covered = set()
            next = deque()

            specials = []

            next.append(zeros)

            while (len(next) > 0):
                l1 = next.popleft()
                covered.add(l1)
                for l2 in ulist:
                    if l2 not in covered and self.difference(l1, l2) == 1:
                        graph[l1].add(l2)

                        if l2 not in next:
                            next.append(l2)

            val = set()
            for v in graph.values():
                val.update(v)

            notmain = [x for x in ulist if x not in val]
            notmain.remove(zeros)
            nums = [sum([int(y) for y in x]) for x in notmain]
            notmain = [x for _, x in sorted(zip(nums, notmain))]

            specials = notmain

            extras = set()

            for nm in notmain:
                comp = set()
                comp.update(val)
                comp.update(extras)

                mindist = 1000
                minli1, minli2 = None, None
                for l in comp:
                    if nm != l:
                        diff = self.difference(nm, l)
                        if diff < mindist:
                            mindist = diff
                            minli = l

                diffbase = self.difference(nm, zeros)
                if diffbase <= mindist:
                    mindist = diffbase
                    minli = zeros

                num1 = sum([int(s) for s in nm])
                num2 = sum([int(s) for s in minli])
                if num1 < num2:
                    graph[nm].add(minli)
                else:
                    graph[minli].add(nm)

                extras.add(nm)

            val = set()
            for v in graph.values():
                val.update(v)
                f2 = open(path_to_dag_results +'relation-tree' + addition + '.dot', 'w')
                f2.write("digraph dag {\n")
                f2.write("rankdir=LR;\n")
                num = 0
                for idx, li in names.items():
                    text = ''
                    name = str(idx) + '\n'

                    for l in li:
                        name += l + ',\n'
                    if idx not in specials:
                        text = str(idx) + " [label=\"" + name + "\" , shape=box;]"
                    else:  # treat in a special way. For now, leaving intact
                        text = str(idx) + " [shape=box label=\"" + name + "\"]"
                    f2.write(text)
                    f2.write('\n')
                for k, v in graph.items():
                    for vi in v:
                        f2.write(str(k) + "->" + str(vi))
                        f2.write('\n')
                f2.write("}")
                f2.close()
            # Rendering DAG

            try:
                filename = path_to_dag_results +'relation-tree' + addition + '.dot'
                # src = Source(source=test)
                # new_name = self.path_to_store + "DAG" + addition + '.png'
                # src.render(new_name, view=True)

                render('dot', 'png', filename)
            except:
                print('Rendering DAG')
                # os.system('dot -Tpng relation-tree' + addition + '.dot -o DAG' + addition + '.png')
                # print('Done')


        # temporal heatmaps start

        print("Writing temporal heatmaps")

        if not os.path.exists(path_to_intermediate_results + "heatmaps" + '/'):
            os.mkdir(path_to_intermediate_results + "heatmaps" + '/')
            os.mkdir(path_to_intermediate_results + "heatmaps" + '/bytes')
            os.mkdir(path_to_intermediate_results + "heatmaps" + '/gaps')
            os.mkdir(path_to_intermediate_results + "heatmaps" + '/sport')
            os.mkdir(path_to_intermediate_results + "heatmaps"+ '/dport')

        actlabels = []
        for a in range(len(values)):  # range(10):
            actlabels.append(mapping[keys[a]])

        clusterinfo = {}
        seqclufile = csv_file
        lines = []
        lines = open(seqclufile).readlines()[1:]

        for line in lines:
            li = line.split(",")  # clusnum, connnum, prob, srcip, dstip

            srcip = li[4]
            dstip = li[5][:-1]
            has = int(li[1])

            name = str('%12s->%12s' % (srcip, dstip))
            if li[0] not in clusterinfo.keys():
                clusterinfo[li[0]] = []
            clusterinfo[li[0]].append((has, name))

        sns.set(font_scale=0.9)
        matplotlib.rcParams.update({'font.size': 10})
        for names, sname, q in [("Packet sizes", "bytes", 1), ("Interval", "gaps", 0), ("Source Port", "sport", 3),
                                ("Dest. Port", "dport", 4)]:
            for clusnum, cluster in clusterinfo.items():
                items = [int(x[0]) for x in cluster]
                labels = [x[1] for x in cluster]

                acha = [actlabels.index(int(x[0])) for x in cluster]

                blah = [values[a] for a in acha]

                dataf = []

                for b in blah:
                    dataf.append([x[q] for x in b][:self.window_size])

                df = pd.DataFrame(dataf, index=labels)

                g = sns.clustermap(df, xticklabels=False, col_cluster=False)  # , vmin= minb, vmax=maxb)
                ind = g.dendrogram_row.reordered_ind
                fig = plt.figure(figsize=(10.0, 9.0))
                plt.suptitle("Exp: " + self.expname + " | Cluster: " + clusnum + " | Feature: " + names)
                ax = fig.add_subplot(111)
                datanew = []
                labelsnew = []
                lol = []
                for it in ind:
                    labelsnew.append(labels[it])
                    lol.append(cluster[[x[1] for x in cluster].index(labels[it])][0])

                acha = [actlabels.index(int(x)) for x in lol]
                blah = [values[a] for a in acha]

                dataf = []

                for b in blah:
                    dataf.append([x[q] for x in b][:20])
                df = pd.DataFrame(dataf, index=labelsnew)
                g = sns.heatmap(df, xticklabels=False)
                plt.setp(g.get_yticklabels(), rotation=0)
                plt.subplots_adjust(top=0.92, bottom=0.02, left=0.25, right=1, hspace=0.94)
                plt.savefig(path_to_intermediate_results + "heatmaps" + "/" + sname + "/" + clusnum)

                plt.close()
                plt.clf()


        ####################
        # Summary Creation #
        ####################

        print("Creating summary file")

        summary_file = self.path_to_store + "summary" + addition + '.txt'

        summary_csv_df = pd.read_csv(csv_file)

        time_for_processing = end_time - start_time

        total_number_connections = len(summary_csv_df.index)
        total_number_packets = total_number_connections * self.window_size

        number_of_clusters = len(summary_csv_df["clusnum"].unique())
        avg_size_of_cluster = int(summary_csv_df.groupby("clusnum")["label"].count().mean())
        std_size_of_cluster = round(summary_csv_df.groupby("clusnum")["label"].count().std(), 2)

        number_of_connections_in_noise_cluster = summary_csv_df[summary_csv_df["clusnum"] == -1]["clusnum"].count()
        noise_percentage = round(number_of_connections_in_noise_cluster / total_number_connections, 3)

        total_number_unknown_connection = summary_csv_df[summary_csv_df["label"] == "Unknown"]["clusnum"].count()

        if total_number_unknown_connection > 0:
            unknown_connections_in_noise_cluster = \
            summary_csv_df[(summary_csv_df["label"] == "Unknown") & (summary_csv_df["clusnum"] == -1)]["clusnum"].count()
            percentage_total_unknown_in_noise_cluster = round(
                unknown_connections_in_noise_cluster / total_number_unknown_connection, 3)

            percentage_unknown_of_noise_cluster = round(
                summary_csv_df[summary_csv_df["clusnum"] == -1]["label"].value_counts(normalize=True)["Unknown"], 3)

        else:
            unknown_connections_in_noise_cluster = "nan"
            percentage_total_unknown_in_noise_cluster = "nan"
            percentage_unknown_of_noise_cluster = "nan"

        percentage_detailed_labels_in_noise_cluster = round((summary_csv_df[
                                                                 (summary_csv_df["detailed_label"] != "-") & (
                                                                             summary_csv_df["clusnum"] == -1)][
                                                                 "clusnum"].count()) / (
                                                                summary_csv_df[summary_csv_df["detailed_label"] != "-"][
                                                                    "clusnum"].count()), 3)

        per_cluster_label_count = summary_csv_df.groupby("clusnum")["label"].value_counts(normalize=True)
        max_label_per_cluster = per_cluster_label_count.groupby("clusnum").idxmax().to_frame().reset_index()
        max_label_per_cluster["label"] = max_label_per_cluster["label"].apply(lambda x: x[1])

        max_percentage_per_cluster = per_cluster_label_count.groupby("clusnum").max().to_frame().reset_index()
        max_percentage_per_cluster = max_percentage_per_cluster.rename(columns={"label": "percentage"})
        merged_df_1 = max_label_per_cluster.merge(right=max_percentage_per_cluster, on="clusnum")

        connections_per_cluster = summary_csv_df.groupby("clusnum")["label"].count().to_frame().reset_index()
        connections_per_cluster = connections_per_cluster.rename(columns={"label": "packet_count"})
        connections_per_cluster["relative_packet_count"] = connections_per_cluster["packet_count"].apply(
            lambda x: x / total_number_connections)
        merged_df_2 = merged_df_1.merge(right=connections_per_cluster, on="clusnum")

        merged_df_2["av_cluster_purity"] = merged_df_2["percentage"] * merged_df_2["relative_packet_count"]
        average_cluster_purity = round(merged_df_2["av_cluster_purity"].sum(), 3)

        detailed_labels_present = summary_csv_df["detailed_label"].unique()
        detailed_labels_present = np.delete(detailed_labels_present, np.where(detailed_labels_present == "-"))
        avg_detailed_label_separation_list = []

        for detailed_label in detailed_labels_present:
            detailled_label_count_per_cluster = \
            summary_csv_df[summary_csv_df["detailed_label"] == detailed_label].groupby("clusnum")[
                "detailed_label"].count().to_frame().reset_index()
            detailled_label_count_per_cluster_as_tuple = list(
                detailled_label_count_per_cluster.itertuples(index=False, name=None))

            max_value = 0
            total_count = 0
            for clusname, count_detailed_labels in detailled_label_count_per_cluster_as_tuple:
                if count_detailed_labels > max_value:
                    max_value = count_detailed_labels
                total_count = total_count + count_detailed_labels
            separation = max_value / total_count
            avg_detailed_label_separation_list.append((separation, total_count))

        total_count_detailed_labels = summary_csv_df[summary_csv_df["detailed_label"] != "-"]["clusnum"].count()
        avg_detailed_label_cohesion = round(
            sum(list(map((lambda x: x[0] * x[1]), avg_detailed_label_separation_list))) / total_count_detailed_labels,
            3)

        avg_cluster_probability = round(summary_csv_df["probability"].mean(), 3)

        with open(summary_file, 'w') as log_file:
            log_file.write("Total Time for processing: " + str(round(time_for_processing, 2)) + "\n")
            log_file.write("Validity index: " + str(round(validity_index, 3)) + "\n")
            log_file.write("Shilouette score: " + str(silhouette_score) + "\n")
            log_file.write("Total number of connections: " + str(total_number_connections) + "\n")
            log_file.write("Total number of packets: " + str(total_number_packets) + "\n")
            log_file.write("Number of clusters: " + str(number_of_clusters) + "\n")
            log_file.write("Average cluster size: " + str(avg_size_of_cluster) + "\n")
            log_file.write("Standard deviation cluster size: " + str(std_size_of_cluster) + "\n")
            log_file.write("Noise percentage: " + str(noise_percentage) + "\n")
            log_file.write("Percentage of all unknown connections that are in the noise cluster: " + str(
                percentage_total_unknown_in_noise_cluster) + "\n")
            log_file.write("Percentage of all connections in noise cluster that are unknown: " + str(
                percentage_unknown_of_noise_cluster) + "\n")
            log_file.write("Percentage of connections with detailed labels that are in noise cluster: " + str(
                percentage_detailed_labels_in_noise_cluster) + "\n")
            log_file.write("Average cluster purity: " + str(average_cluster_purity) + "\n")
            log_file.write("Average detailed label cohesion: " + str(avg_detailed_label_cohesion) + "\n")
            log_file.write("Average cluster probability: " + str(avg_cluster_probability) + "\n")
        log_file.close()


        ###############################
        # Performance Matrix Creation #
        ###############################

        print("Creating performance matrices")

        performance_matrix_folder = path_to_intermediate_results + "/performance_matrices"
        os.mkdir(performance_matrix_folder)

        label_performance_matrix = performance_matrix_folder + "/label_performance_matrix" + addition + ".csv"
        label_performance_matrix_table = performance_matrix_folder + "/label_performance_matrix" + addition + ".png"

        detailed_label_performance_matrix = performance_matrix_folder + "/detailed_label_performance_matrix" + addition + ".csv"
        detailed_label_performance_matrix_table = performance_matrix_folder + "/detailed_label_performance_matrix" + addition + ".png"


        label_df = summary_csv_df.groupby("clusnum")["label"].value_counts().to_frame()
        label_df = label_df.rename(columns={"label": "count"})
        label_df = label_df.reset_index()

        labels = label_df["label"].unique()

        for label in labels:
            lower_label = label.lower()
            label_df[lower_label] = np.where(label_df["label"] == label, label_df["count"], 0)

        label_df = label_df.drop(["count", "label"], axis=1)
        label_df = label_df.rename(columns={"clusnum": "Cluster"})

        columns = label_df.columns.tolist()
        labels = label_df.columns.tolist()
        labels.remove("Cluster")
        clusters = label_df["Cluster"].unique().tolist()

        data = []
        for cluster in clusters:
            cluster_column_data = []
            cluster_column_data.append(cluster)
            for label in labels:
                count = int(label_df[(label_df["Cluster"] == cluster)][label].sum())
                cluster_column_data.append(count)
            data.append(cluster_column_data)

        improved_label_df = pd.DataFrame(data, columns=columns)

        detailed_label_df = summary_csv_df.groupby("clusnum")["detailed_label"].value_counts().to_frame()
        detailed_label_df = detailed_label_df.rename(columns={"detailed_label": "count"})
        detailed_label_df = detailed_label_df.reset_index()

        detailed_labels = detailed_label_df["detailed_label"].unique()

        for detail_label in detailed_labels:
            lower_detail_label = detail_label.lower()
            detailed_label_df[lower_detail_label] = np.where(detailed_label_df["detailed_label"] == detail_label,
                                                             detailed_label_df["count"], 0)

        detailed_label_df = detailed_label_df.drop(["count", "detailed_label"], axis=1)
        detailed_label_df = detailed_label_df.rename(columns={"clusnum": "Cluster"})

        columns = detailed_label_df.columns.tolist()
        labels = detailed_label_df.columns.tolist()
        labels.remove("Cluster")
        clusters = detailed_label_df["Cluster"].unique().tolist()

        data = []
        for cluster in clusters:
            cluster_column_data = []
            cluster_column_data.append(cluster)
            for label in labels:
                count = int(detailed_label_df[(detailed_label_df["Cluster"] == cluster)][label].sum())
                cluster_column_data.append(count)
            data.append(cluster_column_data)

        improved_detail_label_df = pd.DataFrame(data, columns=columns)

        improved_label_df.to_csv(label_performance_matrix, index=False)

        fig, ax = plt.subplots()
        fig.patch.set_visible(False)
        ax.axis('off')
        ax.axis('tight')
        table = ax.table(cellText=improved_label_df.values, colLabels=improved_label_df.columns, loc='center',
                         cellLoc='center')
        table.auto_set_column_width(col=list(range(len(improved_label_df.columns))))
        for (row, col), cell in table.get_celld().items():
            if (row == 0):
                cell.set_text_props(fontproperties=FontProperties(weight='bold'))
        fig.tight_layout()
        plt.savefig(label_performance_matrix_table)
        plt.close()
        plt.clf()

        improved_detail_label_df.to_csv(detailed_label_performance_matrix, index=False)

        reduced_column_size_name = [x[0:10] for x in improved_detail_label_df.columns.tolist()]

        fig, ax = plt.subplots()
        fig.patch.set_visible(False)
        ax.axis('off')
        ax.axis('tight')
        table2 = ax.table(cellText=improved_detail_label_df.values, colLabels=reduced_column_size_name, loc='center',
                          cellLoc='center')
        table2.auto_set_column_width(col=list(range(len(reduced_column_size_name))))
        for (row, col), cell in table2.get_celld().items():
            if (row == 0):
                cell.set_text_props(fontproperties=FontProperties(weight='bold'))
        fig.tight_layout()
        plt.savefig(detailed_label_performance_matrix_table, dpi=1200, bbox_inches='tight')
        plt.close()
        plt.clf()


        ##################
        # Graph Creation #
        #################

        print("Creating graphs")

        graphs_folder = self.path_to_store + "/graphs_folder"
        os.mkdir(graphs_folder)

        summary_csv_df = pd.read_csv(csv_file)

        application_name_graph = graphs_folder + "/application_name_graph" + addition + ".png"
        path_to_application_name_legend_storage = graphs_folder + "/application_name_legend" + addition + ".png"
        path_to_application_name_combined = graphs_folder + "/application_name_combined" + addition + ".png"

        application_category_name_graph = graphs_folder + "/application_category_name_graph" + addition + ".png"
        path_to_application_category_name_legend_storage = graphs_folder + "/application_category_name_legend" + addition + ".png"
        path_to_application_category_name_combined = graphs_folder + "/application_category_name_combined" + addition + ".png"

        label_distribution_graph = graphs_folder + "/label_graph" + addition + ".png"
        path_to_label_legend_storage = graphs_folder + "/label_legend" + addition + ".png"
        path_to_label_combined = graphs_folder + "/label_combined" + addition + ".png"

        detailed_label_distribution_graph = graphs_folder + "/detailed_label_graph" + addition + ".png"
        path_to_detailed_label_legend_storage = graphs_folder + "/detailed_label_legend" + addition + ".png"
        path_to_detailed_label_combined = graphs_folder + "/detailed_label_combined" + addition + ".png"

        name_distribution_graph = graphs_folder + "/name_graph" + addition + ".png"
        path_to_name_legend_storage = graphs_folder + "/name_legend" + addition + ".png"
        path_to_name_combined = graphs_folder + "/name_combined" + addition + ".png"


        ####################
        # application name #
        ####################

        overall_detailed_label_df = summary_csv_df.groupby("clusnum")["application_name"].value_counts().to_frame()
        overall_detailed_label_df = overall_detailed_label_df.rename(columns={"application_name": "count"})
        overall_detailed_label_df = overall_detailed_label_df.reset_index()

        clusters = overall_detailed_label_df["clusnum"].unique().tolist()

        if len(clusters) < 4:
            ncols = len(clusters)
        else:
            ncols = 4
        nrows = math.ceil(len(clusters) / 4)

        fig, ax = plt.subplots(nrows=nrows, ncols=ncols, figsize=(7, 7))

        list_of_names_dfs = []

        for cluster in clusters:
            cluster_df = overall_detailed_label_df[overall_detailed_label_df["clusnum"] == cluster][
                ["application_name", "count"]]
            cluster_df["application_name"] = np.where(cluster_df["count"] <= 4, "Other", cluster_df.application_name)

            cluster_df = cluster_df.groupby("application_name")["count"].aggregate(sum).reset_index().sort_values(
                by=["count"], ascending=False)

            list_of_names_dfs.append(cluster_df)

        detailed_label_name_df = list_of_names_dfs.pop()

        for name_df in list_of_names_dfs:
            detailed_label_name_df = detailed_label_name_df.append(name_df)

        detailed_label_name_df = detailed_label_name_df.groupby("application_name")["count"].aggregate(
            sum).reset_index().sort_values(by=["count"])
        unique_application_category_names = detailed_label_name_df["application_name"].tolist()

        colors = {}
        cmap = cm.tab20c(np.linspace(0, 1, len(unique_application_category_names)))

        for index, color in enumerate(cmap):
            application_name = unique_application_category_names.pop()
            colors[application_name] = color


        for index, cluster in enumerate(clusters):
            cluster_df = overall_detailed_label_df[overall_detailed_label_df["clusnum"] == cluster][
                ["application_name", "count"]]

            cluster_df["application_name"] = np.where(cluster_df["count"] <= 4, "Other",
                                                      cluster_df.application_name)

            cluster_df = cluster_df.groupby("application_name")["count"].aggregate(sum).reset_index().sort_values(
                by=["count"])
            cluster_df["relative_count"] = round((cluster_df["count"] / cluster_df["count"].sum()) * 100, 2)

            if len(clusters) == 1:
                patches, texts = ax.pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                        colors=[colors[key] for key in cluster_df["application_name"]])
                new_labels = self.clean_up_labels(texts)
                ax.clear()
                ax.pie(cluster_df["count"], labels=new_labels,
                       colors=[colors[key] for key in cluster_df["application_name"]],
                       labeldistance=1.15, textprops={'fontsize': 8})
                ax.set_title("Cluster " + str(cluster))

            elif len(clusters) <= 4:
                patches, texts = ax[index].pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                               colors=[colors[key] for key in
                                                       cluster_df["application_name"]],
                                               labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[index].clear()
                ax[index].pie(cluster_df["count"], labels=new_labels,
                              colors=[colors[key] for key in cluster_df["application_name"]],
                              labeldistance=1.15, textprops={'fontsize': 8})
                ax[index].set_title("Cluster " + str(cluster))
            else:
                patches, texts = ax[math.floor(index / 4), index % 4].pie(cluster_df["count"],
                                                                          labels=cluster_df["relative_count"],
                                                                          colors=[colors[key] for key in
                                                                                  cluster_df[
                                                                                      "application_name"]],
                                                                          labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[math.floor(index / 4), index % 4].clear()
                ax[math.floor(index / 4), index % 4].pie(cluster_df["count"], labels=new_labels,
                                                         colors=[colors[key] for key in
                                                                 cluster_df["application_name"]],
                                                         labeldistance=1.15, textprops={'fontsize': 8})
                ax[math.floor(index / 4), index % 4].set_title("Cluster " + str(cluster))

        if len(clusters) % 4 != 0:
            if len(clusters) > 4:
                for missing_axis in range(4 - len(clusters) % 4, 4):
                    ax[nrows - 1, missing_axis].axis('off')

        markers = [plt.Line2D([0, 0], [0, 0], color=color, marker='o', linestyle='') for color in colors.values()]

        plt.suptitle("Application Name Distribution per Cluster", y=0.985, x=0.5, fontweight='bold')

        fig.tight_layout()
        fig.canvas.draw()
        fig.savefig(application_name_graph, dpi=1200)

        legend = plt.legend(handles=markers, labels=colors.keys(), loc=3, framealpha=1, frameon=True,
                            bbox_to_anchor=(2, 0))
        separate_legend = legend.figure
        separate_legend.canvas.draw()
        bbox = legend.get_window_extent()
        bbox = bbox.from_extents(*(bbox.extents + np.array([-4, -4, 4, 4])))
        bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
        fig.savefig(path_to_application_name_legend_storage, dpi=1200, bbox_inches=bbox)
        legend.remove()

        plt.close()
        plt.clf()

        graph_img = Image.open(application_name_graph)
        legend_im = Image.open(path_to_application_name_legend_storage)

        widths_graph = graph_img.width
        heights_graph = graph_img.height

        widths_legend = legend_im.width
        heights_legend = legend_im.height

        if heights_legend > heights_graph:
            resize_percentage = heights_graph / heights_legend
            new_width = int(resize_percentage * widths_legend)

            legend_im = legend_im.resize((new_width, heights_graph), Image.ANTIALIAS)

        total_width = widths_graph + widths_legend

        y_offset = int((heights_graph - heights_legend) / 2)

        combined_im = Image.new('RGB', (total_width, heights_graph), color=(255, 255, 255, 1))
        combined_im.paste(graph_img, (0, 0))
        combined_im.paste(legend_im, (widths_graph, y_offset))
        combined_im.save(path_to_application_name_combined)

        #############################
        # application category name #
        #############################

        overall_detailed_label_df = summary_csv_df.groupby("clusnum")[
            "application_category_name"].value_counts().to_frame()
        overall_detailed_label_df = overall_detailed_label_df.rename(columns={"application_category_name": "count"})
        overall_detailed_label_df = overall_detailed_label_df.reset_index()

        clusters = overall_detailed_label_df["clusnum"].unique().tolist()

        if len(clusters) < 4:
            ncols = len(clusters)
        else:
            ncols = 4
        nrows = math.ceil(len(clusters) / 4)

        fig, ax = plt.subplots(nrows=nrows, ncols=ncols, figsize=(7, 7))

        list_of_names_dfs = []

        for cluster in clusters:
            cluster_df = overall_detailed_label_df[overall_detailed_label_df["clusnum"] == cluster][
                ["application_category_name", "count"]]

            cluster_df = cluster_df.groupby("application_category_name")["count"].aggregate(
                sum).reset_index().sort_values(
                by=["count"], ascending=False)

            list_of_names_dfs.append(cluster_df)

        detailed_label_name_df = list_of_names_dfs.pop()

        for name_df in list_of_names_dfs:
            detailed_label_name_df = detailed_label_name_df.append(name_df)

        detailed_label_name_df = detailed_label_name_df.groupby("application_category_name")["count"].aggregate(
            sum).reset_index().sort_values(by=["count"])
        unique_application_category_names = detailed_label_name_df["application_category_name"].tolist()

        colors = {}
        cmap = cm.gist_rainbow(np.linspace(0, 1, len(unique_application_category_names)))

        for index, color in enumerate(cmap):
            application_name = unique_application_category_names.pop()
            colors[application_name] = color

        for index, cluster in enumerate(clusters):
            cluster_df = overall_detailed_label_df[overall_detailed_label_df["clusnum"] == cluster][
                ["application_category_name", "count"]]

            cluster_df = cluster_df.groupby("application_category_name")["count"].aggregate(
                sum).reset_index().sort_values(
                by=["count"])
            cluster_df["relative_count"] = round((cluster_df["count"] / cluster_df["count"].sum()) * 100, 2)

            if len(clusters) == 1:
                patches, texts = ax.pie(cluster_df["count"], labels=cluster_df["relative_count"],
                       colors=[colors[key] for key in cluster_df["application_category_name"]])
                new_labels = self.clean_up_labels(texts)
                ax.clear()
                ax.pie(cluster_df["count"], labels=new_labels,
                                          colors=[colors[key] for key in cluster_df["application_category_name"]],
                                          labeldistance=1.15, textprops={'fontsize': 8})
                ax.set_title("Cluster " + str(cluster))

            elif len(clusters) <= 4:
                patches, texts = ax[index].pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                                         colors=[colors[key] for key in
                                                                 cluster_df["application_category_name"]],
                                                         labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[index].clear()
                ax[index].pie(cluster_df["count"], labels=new_labels,
                                          colors=[colors[key] for key in cluster_df["application_category_name"]],
                                          labeldistance=1.15, textprops={'fontsize': 8})
                ax[index].set_title("Cluster " + str(cluster))
            else:
                patches, texts = ax[math.floor(index / 4), index % 4].pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                                         colors=[colors[key] for key in
                                                                 cluster_df["application_category_name"]],
                                                         labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[math.floor(index / 4), index % 4].clear()
                ax[math.floor(index / 4), index % 4].pie(cluster_df["count"], labels=new_labels,
                                          colors=[colors[key] for key in cluster_df["application_category_name"]],
                                          labeldistance=1.15, textprops={'fontsize': 8})
                ax[math.floor(index / 4), index % 4].set_title("Cluster " + str(cluster))

            if len(clusters) % 4 != 0:
                if len(clusters) > 4:
                    for missing_axis in range(4 - len(clusters) % 4, 4):
                        ax[nrows - 1, missing_axis].axis('off')

        markers = [plt.Line2D([0, 0], [0, 0], color=color, marker='o', linestyle='') for color in colors.values()]
        fig.subplots_adjust(bottom=0.25)

        plt.suptitle("Application Category Name Distribution per Cluster", y=0.985, x=0.5, fontweight='bold')

        fig.tight_layout()
        fig.canvas.draw()
        fig.savefig(application_category_name_graph, dpi=1200)

        legend = plt.legend(handles=markers, labels=colors.keys(), loc=3, framealpha=1, frameon=True,
                            bbox_to_anchor=(2, 0))
        separate_legend = legend.figure
        separate_legend.canvas.draw()
        bbox = legend.get_window_extent()
        bbox = bbox.from_extents(*(bbox.extents + np.array([-4, -4, 4, 4])))
        bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
        fig.savefig(path_to_application_category_name_legend_storage, dpi=1200, bbox_inches=bbox)
        legend.remove()

        plt.close()
        plt.clf()

        graph_img = Image.open(application_category_name_graph)
        legend_im = Image.open(path_to_application_category_name_legend_storage)

        widths_graph = graph_img.width
        heights_graph = graph_img.height

        widths_legend = legend_im.width
        heights_legend = legend_im.height

        if heights_legend > heights_graph:
            resize_percentage = heights_graph / heights_legend
            new_width = int(resize_percentage * widths_legend)

            legend_im = legend_im.resize((new_width, heights_graph), Image.ANTIALIAS)

        total_width = widths_graph + widths_legend

        y_offset = int((heights_graph - heights_legend) / 2)

        combined_im = Image.new('RGB', (total_width, heights_graph), color=(255, 255, 255, 1))
        combined_im.paste(graph_img, (0, 0))
        combined_im.paste(legend_im, (widths_graph, y_offset))
        combined_im.save(path_to_application_category_name_combined)

        #########
        # label #
        #########

        overall_detailed_label_df = summary_csv_df.groupby("clusnum")["label"].value_counts().to_frame()
        overall_detailed_label_df = overall_detailed_label_df.rename(columns={"label": "count"})
        overall_detailed_label_df = overall_detailed_label_df.reset_index()

        clusters = overall_detailed_label_df["clusnum"].unique().tolist()

        if len(clusters) < 4:
            ncols = len(clusters)
        else:
            ncols = 4
        nrows = math.ceil(len(clusters) / 4)

        fig, ax = plt.subplots(nrows=nrows, ncols=ncols, figsize=(7, 7))

        colors = {}
        colors["Malicious"] = "r"
        colors["Benign"] = "g"
        colors["Unknown"] = "grey"

        for index, cluster in enumerate(clusters):
            cluster_df = \
                overall_detailed_label_df[overall_detailed_label_df["clusnum"] == cluster][
                    ["label", "count"]]

            cluster_df = cluster_df.groupby("label")["count"].aggregate(
                sum).reset_index().sort_values(
                by=["count"])
            cluster_df["relative_count"] = round((cluster_df["count"] / cluster_df["count"].sum()) * 100, 2)

            if (len(cluster_df.index) > 7):
                cluster_df["relative_count"] = np.where(cluster_df["relative_count"] <= 5, "",
                                                        cluster_df["relative_count"])

            if len(clusters) == 1:
                patches, texts = ax.pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                        colors=[colors[key] for key in cluster_df["label"]])
                new_labels = self.clean_up_labels(texts)
                ax.clear()
                ax.pie(cluster_df["count"], labels=new_labels,
                       colors=[colors[key] for key in cluster_df["label"]],
                       labeldistance=1.15, textprops={'fontsize': 8})
                ax.set_title("Cluster " + str(cluster))

            elif len(clusters) <= 4:
                patches, texts = ax[index].pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                               colors=[colors[key] for key in
                                                       cluster_df["label"]],
                                               labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[index].clear()
                ax[index].pie(cluster_df["count"], labels=new_labels,
                              colors=[colors[key] for key in cluster_df["label"]],
                              labeldistance=1.15, textprops={'fontsize': 8})
                ax[index].set_title("Cluster " + str(cluster))
            else:
                patches, texts = ax[math.floor(index / 4), index % 4].pie(cluster_df["count"],
                                                                          labels=cluster_df["relative_count"],
                                                                          colors=[colors[key] for key in
                                                                                  cluster_df[
                                                                                      "label"]],
                                                                          labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[math.floor(index / 4), index % 4].clear()
                ax[math.floor(index / 4), index % 4].pie(cluster_df["count"], labels=new_labels,
                                                         colors=[colors[key] for key in
                                                                 cluster_df["label"]],
                                                         labeldistance=1.15, textprops={'fontsize': 8})
                ax[math.floor(index / 4), index % 4].set_title("Cluster " + str(cluster))

            if len(clusters) % 4 != 0:
                if len(clusters) > 4:
                    for missing_axis in range(4 - len(clusters) % 4, 4):
                        ax[nrows - 1, missing_axis].axis('off')

        markers = [plt.Line2D([0, 0], [0, 0], color=color, marker='o', linestyle='') for color in colors.values()]
        fig.subplots_adjust(bottom=0.25)

        plt.suptitle("Label Distribution per Cluster", y=0.985, x=0.5, fontweight='bold')

        fig.tight_layout()
        fig.canvas.draw()
        fig.savefig(label_distribution_graph, dpi=1200)

        legend = plt.legend(handles=markers, labels=colors.keys(), loc=3, framealpha=1, frameon=True,
                            bbox_to_anchor=(2, 0))
        separate_legend = legend.figure
        separate_legend.canvas.draw()
        bbox = legend.get_window_extent()
        bbox = bbox.from_extents(*(bbox.extents + np.array([-4, -4, 4, 4])))
        bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
        fig.savefig(path_to_label_legend_storage, dpi=1200, bbox_inches=bbox)
        legend.remove()

        plt.close()
        plt.clf()

        graph_img = Image.open(label_distribution_graph)
        legend_im = Image.open(path_to_label_legend_storage)

        widths_graph = graph_img.width
        heights_graph = graph_img.height

        widths_legend = legend_im.width
        heights_legend = legend_im.height

        if heights_legend > heights_graph:
            resize_percentage = heights_graph / heights_legend
            new_width = int(resize_percentage * widths_legend)

            legend_im = legend_im.resize((new_width, heights_graph), Image.ANTIALIAS)

        total_width = widths_graph + widths_legend

        y_offset = int((heights_graph - heights_legend) / 2)

        combined_im = Image.new('RGB', (total_width, heights_graph), color=(255, 255, 255, 1))
        combined_im.paste(graph_img, (0, 0))
        combined_im.paste(legend_im, (widths_graph, y_offset))
        combined_im.save(path_to_label_combined)

        ##################
        # detailed label #
        ##################

        overall_detailed_label_df = summary_csv_df.groupby("clusnum")["detailed_label"].value_counts().to_frame()
        overall_detailed_label_df = overall_detailed_label_df.rename(columns={"detailed_label": "count"})
        overall_detailed_label_df = overall_detailed_label_df.reset_index()

        clusters = overall_detailed_label_df["clusnum"].unique().tolist()

        if len(clusters) < 4:
            ncols = len(clusters)
        else:
            ncols = 4
        nrows = math.ceil(len(clusters) / 4)

        fig, ax = plt.subplots(nrows=nrows, ncols=ncols, figsize=(7, 7))
        list_of_names_dfs = []

        for cluster in clusters:
            cluster_df = overall_detailed_label_df[overall_detailed_label_df["clusnum"] == cluster][
                ["detailed_label", "count"]]
            cluster_df["detailed_label"] = np.where(cluster_df["detailed_label"] == "-", "Unknown",
                                                    cluster_df.detailed_label)

            cluster_df = cluster_df.groupby("detailed_label")["count"].aggregate(sum).reset_index().sort_values(
                by=["count"], ascending=False)

            list_of_names_dfs.append(cluster_df)

        detailed_label_name_df = list_of_names_dfs.pop()

        for name_df in list_of_names_dfs:
            detailed_label_name_df = detailed_label_name_df.append(name_df)

        detailed_label_name_df = detailed_label_name_df.groupby("detailed_label")["count"].aggregate(
            sum).reset_index().sort_values(by=["count"])
        unique_application_category_names = detailed_label_name_df["detailed_label"].tolist()

        colors = {}
        cmap = cm.terrain(np.linspace(0, 1, len(unique_application_category_names)))

        for index, color in enumerate(cmap):
            application_name = unique_application_category_names.pop()
            colors[application_name] = color

        for index, cluster in enumerate(clusters):
            cluster_df = overall_detailed_label_df[overall_detailed_label_df["clusnum"] == cluster][
                ["detailed_label", "count"]]

            cluster_df = cluster_df.groupby("detailed_label")["count"].aggregate(sum).reset_index().sort_values(
                by=["count"])
            cluster_df["relative_count"] = round((cluster_df["count"] / cluster_df["count"].sum()) * 100, 2)

            if len(clusters) == 1:
                patches, texts = ax.pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                        colors=[colors[key] for key in cluster_df["detailed_label"]])
                new_labels = self.clean_up_labels(texts)
                ax.clear()
                ax.pie(cluster_df["count"], labels=new_labels,
                       colors=[colors[key] for key in cluster_df["detailed_label"]],
                       labeldistance=1.15, textprops={'fontsize': 8})
                ax.set_title("Cluster " + str(cluster))

            elif len(clusters) <= 4:
                patches, texts = ax[index].pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                               colors=[colors[key] for key in
                                                       cluster_df["detailed_label"]],
                                               labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[index].clear()
                ax[index].pie(cluster_df["count"], labels=new_labels,
                              colors=[colors[key] for key in cluster_df["detailed_label"]],
                              labeldistance=1.15, textprops={'fontsize': 8})
                ax[index].set_title("Cluster " + str(cluster))
            else:
                patches, texts = ax[math.floor(index / 4), index % 4].pie(cluster_df["count"],
                                                                          labels=cluster_df["relative_count"],
                                                                          colors=[colors[key] for key in
                                                                                  cluster_df[
                                                                                      "detailed_label"]],
                                                                          labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[math.floor(index / 4), index % 4].clear()
                ax[math.floor(index / 4), index % 4].pie(cluster_df["count"], labels=new_labels,
                                                         colors=[colors[key] for key in
                                                                 cluster_df["detailed_label"]],
                                                         labeldistance=1.15, textprops={'fontsize': 8})
                ax[math.floor(index / 4), index % 4].set_title("Cluster " + str(cluster))

            if len(clusters) % 4 != 0:
                if len(clusters) > 4:
                    for missing_axis in range(4 - len(clusters) % 4, 4):
                        ax[nrows - 1, missing_axis].axis('off')

        markers = [plt.Line2D([0, 0], [0, 0], color=color, marker='o', linestyle='') for color in colors.values()]
        fig.subplots_adjust(bottom=0.25)

        plt.suptitle("Detailed Label Distribution per Cluster", y=0.985, x=0.5, fontweight='bold')

        fig.tight_layout()
        fig.canvas.draw()
        fig.savefig(detailed_label_distribution_graph, dpi=1200)

        legend = plt.legend(handles=markers, labels=colors.keys(), loc=3, framealpha=1, frameon=True,
                            bbox_to_anchor=(2, 0))
        separate_legend = legend.figure
        separate_legend.canvas.draw()
        bbox = legend.get_window_extent()
        bbox = bbox.from_extents(*(bbox.extents + np.array([-4, -4, 4, 4])))
        bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
        fig.savefig(path_to_detailed_label_legend_storage, dpi=1200, bbox_inches=bbox)
        legend.remove()

        plt.close()
        plt.clf()

        graph_img = Image.open(detailed_label_distribution_graph)
        legend_im = Image.open(path_to_detailed_label_legend_storage)

        widths_graph = graph_img.width
        heights_graph = graph_img.height

        widths_legend = legend_im.width
        heights_legend = legend_im.height

        if heights_legend > heights_graph:
            resize_percentage = heights_graph / heights_legend
            new_width = int(resize_percentage * widths_legend)

            legend_im = legend_im.resize((new_width, heights_graph), Image.ANTIALIAS)

        total_width = widths_graph + widths_legend

        y_offset = int((heights_graph - heights_legend) / 2)

        combined_im = Image.new('RGB', (total_width, heights_graph), color=(255, 255, 255, 1))
        combined_im.paste(graph_img, (0, 0))
        combined_im.paste(legend_im, (widths_graph, y_offset))
        combined_im.save(path_to_detailed_label_combined)

        ########
        # name #
        ########

        overall_name_df = summary_csv_df.groupby("clusnum")["name"].value_counts().to_frame()
        overall_name_df = overall_name_df.rename(columns={"name": "count"})
        overall_name_df = overall_name_df.reset_index()

        clusters = overall_name_df["clusnum"].unique().tolist()

        if len(clusters) < 4:
            ncols = len(clusters)
        else:
            ncols = 4
        nrows = math.ceil(len(clusters) / 4)

        fig, ax = plt.subplots(nrows=nrows, ncols=ncols, figsize=(7, 7))
        list_of_names_dfs = []

        for cluster in clusters:
            cluster_df = overall_name_df[overall_name_df["clusnum"] == cluster][
                ["name", "count"]]

            cluster_df = cluster_df.groupby("name")["count"].aggregate(sum).reset_index().sort_values(
                by=["count"], ascending=False)

            list_of_names_dfs.append(cluster_df)

        detailed_label_name_df = list_of_names_dfs.pop()

        for name_df in list_of_names_dfs:
            detailed_label_name_df = detailed_label_name_df.append(name_df)

        detailed_label_name_df = detailed_label_name_df.groupby("name")["count"].aggregate(
            sum).reset_index().sort_values(by=["count"])
        unique_application_category_names = detailed_label_name_df["name"].tolist()

        colors = {}
        cmap = cm.ocean(np.linspace(0, 1, len(unique_application_category_names)))

        for index, color in enumerate(cmap):
            application_name = unique_application_category_names.pop()
            colors[application_name] = color

        for index, cluster in enumerate(clusters):
            cluster_df = overall_name_df[overall_name_df["clusnum"] == cluster][
                ["name", "count"]]

            cluster_df = cluster_df.groupby("name")["count"].aggregate(sum).reset_index().sort_values(
                by=["count"])
            cluster_df["relative_count"] = round((cluster_df["count"] / cluster_df["count"].sum()) * 100, 2)

            if len(clusters) == 1:
                patches, texts = ax.pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                        colors=[colors[key] for key in cluster_df["name"]])
                new_labels = self.clean_up_labels(texts)
                ax.clear()
                ax.pie(cluster_df["count"], labels=new_labels,
                       colors=[colors[key] for key in cluster_df["name"]],
                       labeldistance=1.15, textprops={'fontsize': 8})
                ax.set_title("Cluster " + str(cluster))

            elif len(clusters) <= 4:
                patches, texts = ax[index].pie(cluster_df["count"], labels=cluster_df["relative_count"],
                                               colors=[colors[key] for key in
                                                       cluster_df["name"]],
                                               labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[index].clear()
                ax[index].pie(cluster_df["count"], labels=new_labels,
                              colors=[colors[key] for key in cluster_df["name"]],
                              labeldistance=1.15, textprops={'fontsize': 8})
                ax[index].set_title("Cluster " + str(cluster))
            else:
                patches, texts = ax[math.floor(index / 4), index % 4].pie(cluster_df["count"],
                                                                          labels=cluster_df["relative_count"],
                                                                          colors=[colors[key] for key in
                                                                                  cluster_df[
                                                                                      "name"]],
                                                                          labeldistance=1.25)
                new_labels = self.clean_up_labels(texts)
                ax[math.floor(index / 4), index % 4].clear()
                ax[math.floor(index / 4), index % 4].pie(cluster_df["count"], labels=new_labels,
                                                         colors=[colors[key] for key in
                                                                 cluster_df["name"]],
                                                         labeldistance=1.15, textprops={'fontsize': 8})
                ax[math.floor(index / 4), index % 4].set_title("Cluster " + str(cluster))

            if len(clusters) % 4 != 0:
                if len(clusters) > 4:
                    for missing_axis in range(4 - len(clusters) % 4, 4):
                        ax[nrows - 1, missing_axis].axis('off')

        markers = [plt.Line2D([0, 0], [0, 0], color=color, marker='o', linestyle='') for color in colors.values()]
        fig.subplots_adjust(bottom=0.25)

        plt.suptitle("Device / Malware Distribution per Cluster", y=0.985, x=0.5, fontweight='bold')

        fig.tight_layout()
        fig.canvas.draw()
        fig.savefig(name_distribution_graph, dpi=1200)

        legend = plt.legend(handles=markers, labels=colors.keys(), loc=3, framealpha=1, frameon=True,
                            bbox_to_anchor=(2, 0))
        separate_legend = legend.figure
        separate_legend.canvas.draw()
        bbox = legend.get_window_extent()
        bbox = bbox.from_extents(*(bbox.extents + np.array([-4, -4, 4, 4])))
        bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
        fig.savefig(path_to_name_legend_storage, dpi=1200, bbox_inches=bbox)
        legend.remove()

        plt.close()
        plt.clf()

        graph_img = Image.open(name_distribution_graph)
        legend_im = Image.open(path_to_name_legend_storage)

        widths_graph = graph_img.width
        heights_graph = graph_img.height

        widths_legend = legend_im.width
        heights_legend = legend_im.height

        if heights_legend > heights_graph:
            resize_percentage = heights_graph / heights_legend
            new_width = int(resize_percentage * widths_legend)

            legend_im = legend_im.resize((new_width, heights_graph), Image.ANTIALIAS)

        total_width = widths_graph + widths_legend

        y_offset = int((heights_graph - heights_legend) / 2)

        combined_im = Image.new('RGB', (total_width, heights_graph), color=(255, 255, 255, 1))
        combined_im.paste(graph_img, (0, 0))
        combined_im.paste(legend_im, (widths_graph, y_offset))
        combined_im.save(path_to_name_combined)

    def clean_up_labels(self, texts):

        amount_skip = 0
        new_labels = []
        for text_index, text in enumerate(texts):
            if (text_index == 0):
                new_labels.append(text.get_text())
            else:
                current_xy = text.get_position()
                current_str = text.get_text()

                past_text = texts[text_index - 1]
                past_xy = past_text.get_position()
                past_str = new_labels[text_index - 1]

                distance = math.sqrt(
                    pow((current_xy[0] - past_xy[0]), 2) + pow((current_xy[1] - past_xy[1]), 2))

                if distance < 0.3:
                    if distance < 0.2:
                        if amount_skip < 2:
                            new_labels.append(" ")
                            amount_skip = amount_skip + 1
                        else:
                            new_labels.append(current_str)
                            amount_skip = 0
                    else:
                        if past_str != " ":
                            new_labels.append(" ")
                            amount_skip = amount_skip + 1
                        else:
                            new_labels.append(current_str)
                            amount_skip = 0
                else:
                    new_labels.append(current_str)
                    amount_skip = 0

        return new_labels

    def inet_to_str(self, inet):
        """Convert inet object to a string
            Args:
                inet (inet struct): inet network address
            Returns:
                str: Printable/readable IP address
        """
        # First try ipv4 and then ipv6
        try:
            return socket.inet_ntop(socket.AF_INET, inet)
        except ValueError:
            return socket.inet_ntop(socket.AF_INET6, inet)


    src_set, dst_set, gap_set, proto_set, bytes_set, events_set, ip_set, dns_set, port_set = set(), set(), set(), set(), set(), set(), set(), set(), set()
    src_dict, dst_dict, proto_dict, events_dict, dns_dict, port_dict = {}, {}, {}, {}, {}, {}
    bytes, gap_list = [], []


    def readpcap_window(self, filename):

        print("Window mode")
        print("Reading", os.path.basename(filename))
        mal = 0
        ben = 0
        tot = 0
        counter = 0
        ipcounter = 0
        tcpcounter = 0
        udpcounter = 0

        data = []
        connections = {}
        packetspersecond = []
        bytesperhost = {}
        count = 0
        previousTimestamp = {}
        bytespersec = 0
        gaps = []
        incoming = []
        outgoing = []
        period = 0
        bla = 0
        f = open(filename, 'rb')
        pcap = dpkt.pcap.Reader(f)
        for ts, pkt in pcap:
            counter += 1
            eth = None
            bla += 1
            try:
                eth = dpkt.ethernet.Ethernet(pkt)
            except:
                continue

            if eth.type != dpkt.ethernet.ETH_TYPE_IP:
                continue

            ip = eth.data

            src_ip = self.inet_to_str(ip.src)
            dst_ip = self.inet_to_str(ip.dst)

            key = (src_ip, dst_ip)

            timestamp = datetime.datetime.utcfromtimestamp(ts)

            if key in previousTimestamp:
                gap = (timestamp - previousTimestamp[key]).microseconds / 1000
            else:
                gap = 0

            previousTimestamp[key] = timestamp

            tupple = (gap, ip.len, ip.p)

            gaps.append(tupple)

            sport = 0
            dport = 0

            try:
                if ip.p == dpkt.ip.IP_PROTO_TCP or ip.p == dpkt.ip.IP_PROTO_UDP:
                    sport = ip.data.sport
                    dport = ip.data.dport
            except:
                continue

            if key not in connections.keys():
                connections[key] = []
            connections[key].append((gap, ip.len, ip.p, sport, dport))

        print(os.path.basename(filename), " num connections: ", len(connections))

        values = []
        todel = []
        print('Before cleanup: Total packets: ', len(gaps), ' in ', len(connections), ' connections.')

        final_connections = {}

        for (src_ip, dst_ip), packets in connections.items():  # clean it up
            src_ip = src_ip
            dst_ip = dst_ip

            window = 0
            loop_packet_list = []

            for index, packet in enumerate(packets):
                loop_packet_list.append(packet)
                if len(loop_packet_list) == self.window_size:
                    final_connections[(src_ip, dst_ip, str(window))] = loop_packet_list
                    loop_packet_list = []
                    window = window + 1


        print("Remaining connections after clean up ", len(connections))

        return (gaps, final_connections)

    def readfolde_window(self):
        fno = 0
        meta = {}
        mapping = {}
        files = glob.glob(self.path_to_folder + "/*.pcap")
        print('About to read pcap...')
        for f in files:
            key = os.path.basename(f)  # [:-5].split('-')

            data, connections = self.readpcap_window(f)
            if len(connections.items()) < 1:
                continue

            for i, v in connections.items():
                name = key + "->" + i[0] + "->" + i[1] + "->" + i[2]
                mapping[name] = fno
                fno += 1
                meta[name] = v

            print("Average conn length: ", np.mean([len(x) for i, x in connections.items()]))
            print("Minimum conn length: ", np.min([len(x) for i, x in connections.items()]))
            print("Maximum conn length: ", np.max([len(x) for i, x in connections.items()]))
            print('----------------')

        print('++++++++++++++++')
        print('----------------')
        print('Done reading pcaps...')
        print('Collective surviving connections ', len(meta))

        self.connlevel_sequence(meta, mapping)


    def readfile(self, path_to_pcap_file):
        startf = time.time()
        mapping = {}
        print('About to read pcap...')
        data, connections = self.readpcap(path_to_pcap_file)
        print('Done reading pcaps...')
        if len(connections.items()) < 1:
            return

        endf = time.time()
        print('file reading ', (endf - startf))
        fno = 0
        meta = {}
        nconnections = {}
        print("Average conn length: ", np.mean([len(x) for i, x in connections.items()]))
        print("Minimum conn length: ", np.min([len(x) for i, x in connections.items()]))
        print("Maximum conn length: ", np.max([len(x) for i, x in connections.items()]))

        for i, v in connections.items():
            name = i[0] + "->" + i[1]
            mapping[name] = fno
            fno += 1
            meta[name] = v
        print('Surviving connections ', len(meta))
        startc = time.time()
        self.connlevel_sequence(meta, mapping)
        endc = time.time()
        print('Total time ', (endc - startc))
