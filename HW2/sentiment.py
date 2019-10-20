import numpy as np
import matplotlib.pyplot as plt
import torch
from torch import nn
import torch.nn.functional as F
import os
import pickle
import sys
import time

VEC_DIM = 200
LR = 0.4
ITERATION = 15
BATCH_SIZE = 1
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu") #torch.device("cpu") #

def glove2file():
    words = []
    idx = 0
    word2idx = {}
    vectors = []
    with open("glove.6B/glove.6B." + str(VEC_DIM) + "d.txt", 'rb') as f:
        for l in f:
            line = l.split()
            word = line[0].decode()
            words.append(word)
            word2idx[word] = idx
            idx += 1
            vect = np.array(line[1:]).astype(np.float)
            vectors.append(vect)
    pickle.dump(word2idx, open('6B.' + str(VEC_DIM) + '_word2idx.pkl', 'wb'))
    pickle.dump(word2idx, open('6B.' + str(VEC_DIM) + '_words.pkl', 'wb'))
    pickle.dump(vectors, open('6B.' + str(VEC_DIM) + '_vectors.pkl', 'wb'))
    print("glove serializing done")

def file2glove():
    word2idx = pickle.load(open('6B.' + str(VEC_DIM) + '_word2idx.pkl', 'rb'))
    vectors = pickle.load(open('6B.' + str(VEC_DIM) + '_vectors.pkl', 'rb'))
    #words = pickle.load(open('6B.' + str(VEC_DIM) + '_words.pkl', 'rb'))
    return word2idx, vectors

word2idx, vectors = file2glove()
print("glove loading done")

class DAN(nn.Module):
    def __init__(self, vec_dim = 50):
        super(DAN, self).__init__()
        self.dense = nn.Sequential(
            nn.Linear(vec_dim, 1200),
            nn.BatchNorm1d(1200),
            nn.ReLU(),
            nn.Dropout(0.5),

            nn.Linear(1200,900),
            nn.BatchNorm1d(900),
            nn.ReLU(),
            nn.Dropout(0.5),

            nn.Linear(900,600),
            nn.BatchNorm1d(600),
            nn.ReLU(),
            nn.Dropout(0.5),
            
            nn.Linear(600, 2)
        )

    def forward(self, x, length):
        out = torch.sum(x) / length
        out = self.dense(out)
        return out

class RNNLM(nn.Module):
    def __init__(self, vec_dim):
        super(RNNLM, self).__init__()
        #self.conv = nn.Conv1d(vec_dim, 64, 5)
        self.rnn = nn.LSTM(input_size = vec_dim, hidden_size = 4, batch_first = True, bidirectional = False)
        #self.dropout = nn.Dropout(0.5)
        self.linear = nn.Linear(4, 2)

    def initialize(self):
        w = self.rnn.all_weights
        nn.init.xavier_uniform_(w[0][0])
        nn.init.xavier_uniform_(w[0][1])
        #nn.init.xavier_uniform_(w[1][0])
        #nn.init.xavier_uniform_(w[0][1])

    def forward(self, seq, length, hidden = None):
        seq = torch.nn.utils.rnn.pack_padded_sequence(seq, length, batch_first = True)
        output, _ = self.rnn(seq)
        output = torch.nn.utils.rnn.pad_packed_sequence(output, batch_first = True)
        output = self.linear(output[0][:,-1,:])
        return output


#validate_neg_list = os.listdir("HW2/validation/neg")
#validate_pos_list = os.listdir("HW2/validation/pos")

def file2Mat(filelist, prop = "training", label = 'neg'):
    X = []
    Y = []
    labelname = "negative" if label == 'neg' else "positive"
    for files in filelist:
        for l in open("HW2/"+ prop +"/" + label + "/" + files, 'rb'):
            raw_line = l.split()
            line = []
            for w in raw_line:
                word = w.decode('latin1')
                if word not in word2idx:
                    if word[-2:] == '\'s':
                        if word[:-2] in word2idx:
                            line.append(word[:-2])
                            line.append(word[-2:])
                    elif word == 'can\'t':
                        line.append("can")
                        line.append("not")
                    elif word[:-2] == '\'t':
                        if word[:-2] in word2idx:
                            line.append("not")
                            line.append(word[-2:])
                    elif len(word.split('-')) >= 2:
                        for w in word.split('-'):
                            if w in word2idx:
                                line.append(w)
                    else:
                        continue
                else:
                    line.append(word)
            vec = []
            for word in line:
                idx = word2idx[word]
                vec.append(vectors[idx])
            vec = torch.tensor(vec)
            y = 0 if label == 'neg' else 1
            X.append(vec)
            Y.append(y)
    return X, Y

def mean1d(x):
    return torch.mean(x, dim = 0)

def accuracy(model, X, Y, L):
    batch_size = BATCH_SIZE
    acc = 0
    cnt = 0
    for k in range((X.shape[0]-1)//batch_size + 1):
        batch_L = L[k*batch_size:(k+1)*batch_size]
        batch_L, idx = torch.sort(batch_L, descending = True)
        batch_X = X[k*batch_size:(k+1)*batch_size][idx].to(DEVICE)
        batch_Y = Y[k*batch_size:(k+1)*batch_size][idx].to(DEVICE)
        logit = model.forward(batch_X, batch_L).cpu()
        res = np.where(logit[:,0] < logit[:,1], 1, 0)
        acc += np.sum(res == batch_Y.cpu().numpy())
        cnt += res.shape[0]
    acc /= cnt
    return acc

def loadData(prop = 'training', shuffle = False):
    posPath = "HW2/" + prop + "/pos"
    pos_list = os.listdir(posPath)
    negPath = "HW2/" + prop + "/neg"
    neg_list = os.listdir(negPath)
    X_p, Y_p = file2Mat(pos_list, prop, 'pos')
    X_n, Y_n = file2Mat(neg_list, prop, 'neg')
    X = X_p + X_n
    l = torch.tensor(list(map(len, sorted(X, key = len, reverse = True)))).long()
    X = torch.nn.utils.rnn.pad_sequence(X, batch_first=True).float()
    Y = torch.tensor(Y_p + Y_n).float()
    if shuffle:
        idx = np.random.permutation(range(len(X)))
        X = X[idx]
        Y = Y[idx]
        l = l[idx]
    return X, Y, l

def data2file(dataset = 'training'):
    name = 'train' if dataset == 'training' else 'test'
    X, Y, length = loadData(dataset, shuffle = True)
    pickle.dump((X, Y, length), open(name + str(VEC_DIM) + '.pkl', 'wb'))
    return X, Y, length


def train(model, learning_rate = 0.001, optimizer = "SGD", batch_size = 20, iterations = 1000, seed = 1):
    opt_name = "SGD" if optimizer == "SGD" else "Adam"
    torch.manual_seed(seed)
    if optimizer == "Adam":
        optimizer = torch.optim.Adam(model.parameters(), lr = learning_rate)
    else:
        optimizer = torch.optim.SGD(model.parameters(), lr = learning_rate)
    model.to(DEVICE)
    model.initialize()

    
    #train_X, train_Y, train_length = data2file('training')
    
    train_X, train_Y, train_length = pickle.load(open('train' + str(VEC_DIM) + '.pkl', 'rb'))
    test_X, test_Y, test_length = pickle.load(open('test' + str(VEC_DIM) + '.pkl', 'rb'))
    print("data loading done")

    print("GPU loading failed") if DEVICE == torch.device("cpu") else print("GPU loading successful")

    losses = []
    train_errors = []
    test_errors = []
    
    train_start_time = time.perf_counter()
    for epoch in range(ITERATION):
        for k in range((train_X.shape[0]-1)//batch_size + 1):
            model.train()
            optimizer.zero_grad()
            model.zero_grad()

            batch_L = train_length[k*batch_size:(k+1)*batch_size]
            batch_L, idx = torch.sort(batch_L, descending = True)
            batch_L = batch_L.to(DEVICE)
            batch_X = train_X[k*batch_size:(k+1)*batch_size][idx].to(DEVICE)
            batch_Y = train_Y[k*batch_size:(k+1)*batch_size][idx].to(DEVICE)

            logit = model.forward(batch_X, batch_L)
            loss = F.cross_entropy(logit, batch_Y.long())
            
            loss.backward()
            optimizer.step()

        losses.append(loss.item())
        if (epoch+1)%10 == 0:
            print("The training loss on Epoch {:d} is {:.3f}".format(epoch+1, loss.item()))
        
        '''
        acc_train = accuracy(model, train_X, train_Y, train_length)
        acc_test = accuracy(model, test_X, test_Y, test_length)
        if (epoch+1)%10 == 0:
            print("The accuracy on testing dataset is {:.3f} and on training dataset is {:.3f}".format(acc_test, acc_train))
        
        train_errors.append(acc_train)
        test_errors.append(acc_test)
        '''
        
    train_stop_time = time.perf_counter()
    
    print("Total Training Time: ", train_stop_time - train_start_time)
    model.eval()

    acc = accuracy(model, train_X, train_Y, train_length)
    print("Accuracy on training dataset is {:5f}".format(acc))
    del train_X
    del train_Y
    del train_length

    #test_X, test_Y, test_length = data2file('testing')
    
    print("test loading successful")
    acc = accuracy(model, test_X, test_Y, test_length)
    print("Accuracy on testing dataset is {:5f}".format(acc))
    del test_X
    del test_Y
    del test_length
    '''
    plt.figure()
    plt.xlabel("Iteration number K")
    plt.ylabel("cross entropy loss")
    plt.plot(range(1, len(losses)+1), losses)
    #plt.show()
    plt.savefig("losses" + opt_name + str(learning_rate) + ".jpg")
    
    
    plt.figure()
    plt.xlabel("Iteration number")
    plt.ylabel("Accuracy")
    plt.plot(range(1, len(train_errors)+1), train_errors, label = "training accuracy")
    plt.plot(range(1, len(test_errors)+1), test_errors, label = "testing accuracy")
    plt.legend()
    #plt.show()
    plt.savefig("errors" + opt_name + str(learning_rate) + ".jpg")
    '''
    return acc
for OPT in ['SGD', 'Adam']:
    for LR in [0.07, 0.05, 0.03, 0.01, 0.005]:
        model = RNNLM(vec_dim = VEC_DIM).to(DEVICE)
        print(model)
        print("Optimizer is {}, Embedding in {:d} dim, and LR = {:.3f}".format(OPT, VEC_DIM, LR))
        print("test vector dim: ", vectors[0].shape)
        train(model, learning_rate = LR, optimizer = OPT, batch_size = BATCH_SIZE, iterations = ITERATION)

        del model

'''
if __name__ == 'main':
    if len(sys.argv) == 1:
        model = DAN(vec_dim = VEC_DIM).to(DEVICE)
        train(model, learning_rate = LR, optimizer = OPT, batch_size = BATCH_SIZE, iterations = ITERATION)
    elif len(sys.argv) == 2:
        model = pickle.load(open('model.torch', 'rb'))
'''