import numpy as np
import math
import pickle
from matplotlib import pyplot as plt 

# A(N,N), B(N,M), pi(N), O(T), N is # states, M is the # observations, T is the # time intervals
# probs have been in log form
def Viterbi(A, B, pi, O):
    T = O.shape[0]
    N = A.shape[0]
    M = B.shape[1]
    v = np.array([[float('-inf') for _ in range(N)] for __ in range(T)], dtype = 'float64')
    for i in range(N):
        v[0][i] = pi[i] + B[i][O[0]]
    pre = range(N)
    for t in range(1,T):
        for j in range(N):
            for i in range(N):
                v[t][j] = max(v[t-1][i] + A[i][j], v[t][j])
            v[t][j] += B[j][O[t]]
    return v.argmax(1)

def train(trian_filename):
    labels_map = {}
    words_map = {"UNKA":0}
    label_idx = 0
    word_idx = 1
    with open(trian_filename) as f:
        mix = f.read().split()
        np.random.seed(22)
        known = np.random.choice(mix[::2],  math.floor(len(mix[::2])*0.87))
        words = set(known)
        labels = set(mix[1::2])
        for word in words:
            words_map[word] = word_idx
            word_idx += 1
        for label in labels:
            labels_map[label] = label_idx
            label_idx += 1
    M = len(words_map)
    N = len(labels_map)
    A = np.array([[0 for _ in range(N)] for __ in range(N)], dtype = 'float64')
    B = np.array([[0 for _ in range(M)] for __ in range(N)], dtype = 'float64')
    pi = np.array([0 for _ in range(N)], dtype = 'float64')
    P = np.array([0 for _ in range(N)], dtype = 'float64')
    
    for line in open(trian_filename):
        words = line.split()
        for i in range(len(words[::2])):
            label = words[i*2+1]
            word = words[i*2]
            P[labels_map[label]] += 1
            if i != 0:
                ii = labels_map[words[i*2-1]]
                jj = labels_map[label]
                A[ii][jj] += 1
            else:
                ii = labels_map[label]
                pi[ii] += 1

            jj = labels_map[label]
            if word in words_map:
                oo = words_map[word]
            else:
                oo = 0
            B[jj][oo] += 1

    P = np.log(P) - np.log(sum(P))
    alpha = np.array([0 for _ in range(N)], dtype = 'float64')
    for i in range(N):
        A[i] = np.log(A[i]) - np.log(sum(A[i]))
    for i in range(N):
        alpha[i] = np.log(1 - np.exp(sum(A[i]))) - np.log(sum(np.where(A[i] == float('-inf'), P, 0)))
    for i in range(N):
        A[i] = np.where(A[i] != 0, A[i], alpha[i] + P)
    for j in range(N):
        B[j] = np.log(B[j]) - np.log(sum(B[j]))
    pi = np.log(pi) - np.log(sum(pi))
    alpha0 = np.log(1 - np.exp(sum(pi))) - np.log(sum(np.where(pi == float('-inf'), P, 0)))
    pi = np.where(pi != 0, pi, alpha0 + P)

    return A, B, pi, labels_map, words_map

A, B, pi, labels_map, words_map = train("wsj1-18.training")
f = open("model.pyc", 'wb')
pickle.dump((A, B, pi, labels_map, words_map), f)

