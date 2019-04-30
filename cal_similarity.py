from gensim.models import Word2Vec
# import gensim
import random
import math
import time


# 获得单词表中与word相似度最第rank高的单词
def get_top(word, rank, word_list):
    score = [(similarity[word][other], other) for other in word_list]
    score.sort(reverse=True)
    return score[rank][1]


# 查看某单词与单词表单词的相似度
def get_similarity_based_word_list(word, word_list):
    similarity_list = [(similarity[word][other], other) for other in word_list]
    similarity_list.sort(reverse=True)
    return similarity_list


# 计算单词的LCS
def lcs(word1, word2):
    dp = [([0] * (len(word2) + 1)) for i in range(len(word1) + 1)]
    for i in range(1, len(word1) + 1):
        for j in range(1, len(word2) + 1):
            if word1[i - 1] == word2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]


# 基于LCS计算词形相似度
def lcs_similarity(word1, word2):
    lcs_result = lcs(word1, word2)
    length = min(len(word1), len(word2))
    if lcs_result <= 2:
        return 0.0
    else:
        return 4 / math.pi * math.atan(lcs_result / length)


# 基于LCS与word2vec计算相似度
def get_similarity(word1, word2):
    lcs_sim = lcs_similarity(word1, word2)
    try:
        word2vec_sim = model.wv.similarity(word1, word2)
    except KeyError:
        word2vec_sim = 0.4
    # print("lcs_sim:" + str(lcs_sim))
    # print("word2vec_sim:" + str(word2vec_sim))
    return 0.6 * word2vec_sim + 0.4 * lcs_sim


def sort_word_list(word_list):
    none_similarity = []

    # model中没有的单词
    for item in word_list:
        try:
            a = model.wv[item]
        except KeyError:
            none_similarity.append(item)
    # print(none_similarity)

    # 建立单词相似度字典
    for item1 in word_list:
        s = {}
        for item2 in word_list:
            try:
                s[item2] = get_similarity(item1, item2)
            except KeyError:
                s[item2] = 0
        similarity[item1] = s

    # 重新排序
    ordered_list = []
    word_list_size = len(word_list)
    pre_word = word_list[random.randint(0, word_list_size - 1)]
    while len(ordered_list) < word_list_size:
        next_word = ''
        for rank in range(word_list_size):
            next_word = get_top(pre_word, rank, word_list)
            if next_word in ordered_list:
                continue
            else:
                break
        ordered_list.append(next_word)
        pre_word = next_word

    # final_list = []
    # for i in range(word_list_size):
    #     try:
    #         if i == word_list_size - 1:
    #             final_list.append((ordered_list[i], -1))
    #         else:
    #             final_list.append((ordered_list[i], similarity[ordered_list[i]][ordered_list[i + 1]]))
    #     except KeyError:
    #         final_list.append((ordered_list[i], -1))

    return ordered_list


# model2 = gensim.models.KeyedVectors.load_word2vec_format('GoogleNews-vectors-negative300.bin', binary=True)
model = Word2Vec.load('./text8_model')
similarity = {}

# words = ['absurd', 'claim', 'ridiculous',
#          'crazy', 'acclaim',
#          'proclaim',
#          'speak', 'reclaim',
#          'announce', 'exclaim']

# print(ordered_list)
# print(final_list)
# print(get_similarity('china'))
# print(model.most_similar('level'))
# print(lcs('apple','orange'))
# print(sort_word_list(words))
# print(model.wv.most_similar('absurd'))
