import random
import re
from collections import Counter
from collections import defaultdict

import jieba
import numpy as np
import pandas as pd
from gensim.models import Word2Vec
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import KNeighborsClassifier


def get_w2v_model(filename):
    model = Word2Vec.load(filename)
    return model


def rm_spec(sent):
    ret = re.sub('[\\n\s+\.\!\/_,$%^*(+\"\')]+|[+——\-()?【】《》“”！，。？、~@#￥%……&*（）]+', '', sent)
    if ret:
        return ret
    return ''


def split_sent(sent):
    sents = re.split('[。？！\n]', sent)
    ret = []
    for s in sents:
        sl = jieba.lcut(s)
        slt = []
        for item in sl:
            sr = rm_spec(item)
            if sr:
                slt.append(sr)
        if slt:
            ret.append(' '.join(slt))
    return ret


def process_news_corpus(filename, news, lst):
    di = defaultdict(list)
    xna_lst = []
    count = 0
    with open(filename, 'w', encoding='utf-8') as fout:
        for i, item in enumerate(lst):
            sent = news['content'][item]
            sents = split_sent(sent)
            if sents:
                di[i].append(count)
                count += len(sents)
                di[i].append(count)
                if '新华社' in news['source'][item] or '新华网' in news['source'][item]:
                    xna_lst.append(i)
                fout.write('\n'.join(sents) + '\n')
    return di, xna_lst


def add_more_train_corpus(model, filename):
    sen_list = []
    with open(filename, 'r', encoding='utf-8') as fin:
        for line in fin.readlines():
            sen_list.append(line.split())
    model.train(sentences=sen_list, total_examples=len(sen_list), epochs=1)


def get_index_lst_from_dict(di, lst):
    ret = []
    for i in lst:
        start = di[i][0]
        end = di[i][1]
        for t in range(start, end):
            ret.append(t)
    return ret


def word_freq(corpus_file):
    word_list = []
    with open(corpus_file, 'r', encoding='utf-8') as fin:
        for line in fin.readlines():
            word_list += line.split()
    cc = Counter(word_list)
    num_all = sum(cc.values())

    def get_word_freq(word):
        return cc[word] / num_all

    return get_word_freq


def write_sent_vec_to_file(filename, model, get_wd_freq, corpus_file):
    a = 0.001
    row = model.wv.vector_size
    with open(filename, 'w') as fout:
        with open(corpus_file, 'r', encoding='utf-8') as fin:
            for line in fin.readlines():
                sent_vec = np.zeros(row)
                wd_lst = line.split()
                for wd in wd_lst:
                    try:
                        pw = get_wd_freq(wd)
                        w = a / (a + pw)
                        sent_vec += w * np.array(model.wv[wd])
                    except:
                        pass
                fout.write(' '.join([str(i) for i in sent_vec]))
                fout.write('\n')


def get_all_sent_vec(filename):
    ret = np.fromfile(filename, dtype=np.float, sep=' ')
    return np.reshape(ret, (-1, 100))


def get_list_with_content(news):
    ret = []
    for i in range(len(news)):
        if pd.isna(news['source'][i]) or pd.isna(news['content'][i]):
            continue
        ret.append(i)
    return ret


def get_tfidf_mat(news, lst):
    corpus = []
    for i in lst:
        corpus.append(' '.join(jieba.lcut(news['content'][i])))
    vectorizer = TfidfVectorizer()
    ret = vectorizer.fit_transform(corpus)
    return ret


def get_remain_list(all_samples, part_samples):
    ret = []
    for i in all_samples:
        if i not in part_samples:
            ret.append(i)
    return ret


def lst2file(filename, lst):
    with open(filename, 'w') as fout:
        fout.write('\n'.join([str(i) for i in lst]) + '\n')


# Classify using kNN
def KNNClassifier(mat, xna_trn_lst, otr_trn_lst, xna_test_lst, otr_test_lst):
    X_train = mat[xna_trn_lst + otr_trn_lst, :]
    Y = np.array([0] * mat.shape[0])
    for i in xna_trn_lst:
        Y[i] = 1
    y_train = Y[xna_trn_lst + otr_trn_lst]

    neigh = KNeighborsClassifier(n_neighbors=10)
    neigh.fit(X_train, y_train)

    xna_test = []
    otr_test = []
    for i in range(len(xna_test_lst)):
        xna_test.append(neigh.predict([mat[xna_test_lst[i]]])[0])
    for i in range(len(otr_test_lst)):
        otr_test.append(neigh.predict([mat[otr_test_lst[i]]])[0])
    return xna_test, otr_test


# Import original corpus
news_df = pd.read_csv('sqlResult_1558435.csv', encoding='gb18030')

# Get news list which has source and content
lst_with_content = get_list_with_content(news_df)

# Build news index dict of corpus file, and filter XNA news
index_dict, xna_news_lst = process_news_corpus('news_corpus.txt', news_df, lst_with_content)
otr_news_lst = get_remain_list(list(index_dict.keys()), xna_news_lst)

# Write temp results to file
# with open('index_dict.txt', 'w') as fout:
#     for k in index_dict:
#         fout.write(str(k) + ':' + ','.join([str(i) for i in index_dict[k]]) + '\n')
#
# with open('xna_lst.txt', 'w') as fout:
#     fout.write('\n'.join([str(i) for i in xna_news_lst]))
#     fout.write('\n')

# Set 90% samples for training, 10% for testing
xna_news_sent_lst = get_index_lst_from_dict(index_dict, xna_news_lst)
otr_news_sent_lst = get_index_lst_from_dict(index_dict, otr_news_lst)

samples_n = int(len(xna_news_sent_lst) * 0.9)

xna_samples_train = random.sample(xna_news_sent_lst, samples_n)
xna_samples_test = get_remain_list(xna_news_sent_lst, xna_samples_train)

otr_samples = random.sample(otr_news_sent_lst, len(xna_news_sent_lst))
otr_samples_train = random.sample(otr_samples, samples_n)
otr_samples_test = get_remain_list(otr_samples, otr_samples_train)

print('XNA news amount for training:', len(xna_samples_train))
print('Other news amount for training:', len(otr_samples_train))

# f = open('train_lst.txt', 'w')
# f.write('\n'.join([str(i) for i in xna_train_lst]))
# f.close()

# Get tfidf vector
# tfidf method for large corpus has large memory footprint, better to replace it with w2v embedding
# tfidf_mat = get_tfidf_mat(news_df, lst_with_content).toarray()

w2v_model = get_w2v_model('wiki_w2v.model')
add_more_train_corpus(w2v_model, 'news_corpus.txt')
get_word_prob = word_freq('news_corpus.txt')
write_sent_vec_to_file('sent_vec.txt', w2v_model, get_word_prob, 'news_corpus.txt')
all_sent_mat = get_all_sent_vec('sent_vec.txt')

xna_test_result, otr_test_result = KNNClassifier(all_sent_mat, xna_samples_train, otr_samples_train, xna_samples_test,
                                                 otr_samples_test)
lst2file('xna_test_result.txt', xna_test_result)
lst2file('otr_test_result.txt', otr_test_result)
