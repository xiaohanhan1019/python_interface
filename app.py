import sys

sys.path.append("..")
sys.path.append("./mdx_resolve")
from mdx_resolve.mdict_query import IndexBuilder
from flask import Flask
from flask_restful import reqparse, abort, Api, Resource

from sqlalchemy import Table, Column, Integer, String, ForeignKey, and_, select, func
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
import sqlalchemy.ext.declarative

import functools
import datetime
import base64
import time
import cal_similarity
import requests
import json
import random

app = Flask(__name__)
api = Api(app)

engine = sqlalchemy.create_engine("mysql+pymysql://root:SSZZhh~~!!22@47.103.3.131:3306/word_chain", encoding="utf8",
                                  echo=False)
Base = sqlalchemy.ext.declarative.declarative_base()

# 利用Session对象连接数据库
DBSession = sqlalchemy.orm.sessionmaker(bind=engine)
session = DBSession()

word_wordList = Table('wordList_has_word', Base.metadata,
                      Column('wordList_id', Integer, ForeignKey('wordList.id'), primary_key=True),
                      Column('word_id', Integer, ForeignKey('word.id'), primary_key=True)
                      )

user_wordList = Table('user_like_wordList', Base.metadata,
                      Column('user_id', Integer, ForeignKey('user.id'), primary_key=True),
                      Column('wordList_id', Integer, ForeignKey('wordList.id'), primary_key=True)
                      )


class User(Base):
    __tablename__ = 'user'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    account = sqlalchemy.Column("account", sqlalchemy.String(50), nullable=False)
    password = sqlalchemy.Column("password", sqlalchemy.String(50), nullable=False)
    nickname = sqlalchemy.Column("nickname", sqlalchemy.String(50), nullable=False)
    status = sqlalchemy.Column("status", sqlalchemy.String(255), nullable=True)
    image_url = sqlalchemy.Column("image_url", sqlalchemy.String(255), nullable=True)

    liked_word_list = relationship('WordList',
                                   secondary=user_wordList,
                                   backref=backref('wordList', lazy='dynamic'),
                                   lazy='dynamic'
                                   )


class Word(Base):
    __tablename__ = 'word'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column("name", sqlalchemy.String(50), nullable=False)
    meaning = sqlalchemy.Column("meaning", sqlalchemy.String(255), nullable=False)
    pronounce = sqlalchemy.Column("pronounce", sqlalchemy.String(255), nullable=True)


class WordList(Base):
    __tablename__ = 'wordList'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    user_id = sqlalchemy.Column("user_id", sqlalchemy.Integer, ForeignKey("user.id"), nullable=False)
    name = sqlalchemy.Column("name", sqlalchemy.String(50), nullable=False)
    image_url = sqlalchemy.Column("image_url", sqlalchemy.String(255), nullable=True)
    description = sqlalchemy.Column("description", sqlalchemy.String(255), nullable=True)

    # 级联删除
    words = relationship('Word',
                         secondary=word_wordList,
                         backref=backref('word', lazy='dynamic', cascade="all,delete"),
                         lazy='dynamic'
                         )


class Moment(Base):
    __tablename__ = 'user_learn_wordList_record'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    user_id = sqlalchemy.Column("user_id", sqlalchemy.Integer, ForeignKey("user.id"), nullable=False)
    word_list_id = sqlalchemy.Column("wordList_id", sqlalchemy.Integer, ForeignKey("wordList.id"), nullable=False)
    create_time = sqlalchemy.Column("create_time", sqlalchemy.DateTime, nullable=True,
                                    default=datetime.datetime.now())


class Follow(Base):
    __tablename__ = 'user_follow'

    user_id = sqlalchemy.Column("user_id", sqlalchemy.Integer, ForeignKey("user.id"), primary_key=True, nullable=False)
    follow_user_id = sqlalchemy.Column("follow_user_id", sqlalchemy.Integer,
                                       ForeignKey("user.id"), primary_key=True, nullable=False)


# 按照小写字典序,对搜索结果进行排序
def cmp_ignore_case(s1, s2):
    s1 = s1.lower()
    s2 = s2.lower()
    if s1 < s2:
        return -1
    elif s1 > s2:
        return 1
    return 0


# 转换为json
def to_dict(self):
    return {c.name: getattr(self, c.name, None) for c in self.__table__.columns}


# 获取时间戳
def get_time_stamp():
    ct = time.time()
    local_time = time.localtime(ct)
    data_head = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
    data_secs = (ct - int(ct)) * 1000
    time_stamp = "%s.%03d" % (data_head, data_secs)
    stamp = ("".join(time_stamp.split()[0].split("-")) + "".join(time_stamp.split()[1].split(":"))).replace('.', '')
    return stamp


# 搜索匹配的单词，返回20个
class SearchWord(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('search', type=str, help='your search string', required=True)

    def post(self):
        args = self.parser.parse_args()
        search = args['search']
        builder = IndexBuilder('./mdx_resolve/mdx/Collins.mdx')
        result = sorted(builder.get_mdx_keys(search + "*")[:20], key=functools.cmp_to_key(cmp_ignore_case))
        # todo 优化搜索结果 使其与搜索字符串最匹配
        result_json = []
        try:
            for word_name in result:
                # 这里用One()会有问题
                word = session.query(Word).filter(Word.name == word_name)[0]
                result_json.append(
                    {"id": word.id, "name": word_name, "meaning": word.meaning, "pronounce": word.pronounce})
            session.commit()
            return result_json, 200
        except Exception as e:
            print(e)
            session.rollback()
            return result_json, 400


# 获取单词详细
class WordDetail(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('word', type=str, help='your word', required=True)

    def post(self):
        args = self.parser.parse_args()
        word = args['word']
        builder = IndexBuilder('./mdx_resolve/mdx/Collins.mdx')
        css = builder.mdd_lookup('\\CollinsEC.css')[0].decode()
        result_text = builder.mdx_lookup(word)
        return {'html': result_text[0][:6] + '<meta name="viewport" content="width=device-width,initial-scale=1.0">' +
                        result_text[0][6:], 'css': '<style>' + css + '</style>'}


# 注册接口
class Register(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('account', type=str, help='your account', required=True)
        self.parser.add_argument('password', type=str, help='your password', required=True)

    def post(self):
        args = self.parser.parse_args()
        account = args['account']
        password = args['password']
        user = User(account=account, password=password, nickname=account, status='什么也没有...', image_url='')
        # 判断是否有该用户名
        exist_user_count = session.query(User).filter(User.account == account).count()
        try:
            if exist_user_count == 0:
                session.add(user)
                session.commit()
                return {'msg': '注册成功'}, 200
            else:
                return {'msg': '用户名已存在'}, 401
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 登陆接口
class Login(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('account', type=str, help='your account', required=True)
        self.parser.add_argument('password', type=str, help='your password', required=True)

    def post(self):
        args = self.parser.parse_args()
        account = args['account']
        password = args['password']
        # 判断是否有该用户名
        try:
            exist_user = session.query(User).filter(User.account == account).one()
            session.commit()
            if exist_user.password == password:
                return to_dict(exist_user), 200
            else:
                return {'msg': '密码不正确'}, 401
        except Exception as e:
            session.rollback()
            return {'msg': '用户不存在' + str(e)}, 400


# 获取用户信息
class GetUserInfoById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='your user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        try:
            user = session.query(User).filter(User.id == user_id).one()
            session.commit()
            return to_dict(user), 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 修改用户信息
class EditUserInfoById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='your user id', required=True)
        self.parser.add_argument('nickname', type=str, help='your nickname', required=False)
        self.parser.add_argument('status', type=str, help='your status', required=False)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        nickname = args['nickname']
        status = args['status']
        try:
            user = session.query(User).filter(User.id == user_id).one()
            if nickname is not None:
                user.nickname = nickname
            if status is not None:
                user.status = status
            session.commit()
            return {'msg': '修改成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 新建单词表
class AddWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('wordList_name', type=str, help='word list name', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args["user_id"]
        name = args["wordList_name"]
        word_list = WordList(user_id=user_id, name=name, image_url='', description='什么都没有...')
        try:
            session.add(word_list)
            session.commit()
            add_word_list = session.query(WordList).filter(WordList.id == word_list.id).one()
            owner = session.query(User).filter(User.id == user_id).one()
            session.commit()
            json = {
                'id': add_word_list.id,
                'name': add_word_list.name,
                'words': [],
                'image_url': add_word_list.image_url,
                'description': add_word_list.description,
                'ownerImage_url': owner.image_url,
                'ownerName': owner.nickname,
                'user_id': owner.id
            }
            return json, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 修改单词表
class EditWordListById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('wordList_id', type=int, help='wordList id', required=True)
        self.parser.add_argument('name', type=str, help='name', required=False)
        self.parser.add_argument('description', type=str, help='description', required=False)
        self.parser.add_argument('image_url', type=str, help='image url', required=False)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['wordList_id']
        name = args['name']
        description = args['description']
        image_url = args['image_url']
        try:
            word_list = session.query(WordList).filter(WordList.id == word_list_id).one()
            if name is not None:
                word_list.name = name
            if description is not None:
                word_list.description = description
            if image_url is not None:
                word_list.image_url = image_url
            session.commit()
            return {'msg': '修改成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 删除单词表
# 删除单词表只是该单词表不属于该用户，数据需要保存，否则别的用户收藏了就会出问题
class DelWordListById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['wordList_id']
        try:
            # user_id = 8
            word_list = session.query(WordList).filter(WordList.id == word_list_id).update({"user_id": 8})
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


class SearchWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('search', type=str, help='your search string', required=True)

    def post(self):
        args = self.parser.parse_args()
        search = args['search']
        try:
            word_lists = session.query(WordList).filter(WordList.name.like('%' + search + '%')).all()
            result = []
            for word_list in word_lists:
                user = session.query(User).filter(User.id == word_list.user_id).one()
                result_word_list = {
                    'id': word_list.id,
                    'name': word_list.name,
                    'words': [],
                    'image_url': word_list.image_url,
                    'description': word_list.description,
                    'ownerName': user.nickname,
                    'ownerImage_url': user.image_url,
                    'user_id': user.id
                }
                words = word_list.words.all()
                for word in words:
                    result_word_list['words'].append(to_dict(word))
                result.append(result_word_list)
            session.commit()
            return result, 200
        except Exception as e:
            print(e)
            session.rollback()
            return {"msg": str(e)}, 400


# 获取用户所有单词表
class GetAllUserWordListByUserId(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        try:
            user = session.query(User).filter(User.id == user_id).one()
            word_lists = session.query(WordList).filter(WordList.user_id == user_id).all()
            result = []
            for word_list in word_lists:
                result_word_list = {
                    'id': word_list.id,
                    'name': word_list.name,
                    'words': [],
                    'image_url': word_list.image_url,
                    'description': word_list.description,
                    'ownerName': user.nickname,
                    'ownerImage_url': user.image_url,
                    'user_id': user.id
                }
                words = word_list.words.all()
                for word in words:
                    result_word_list['words'].append(to_dict(word))
                result.append(result_word_list)
            session.commit()
            return result, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 单词表添加单词
class AddWordToWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)
        self.parser.add_argument('word_id', type=int, help='word id', required=True)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['wordList_id']
        word_id = args['word_id']
        try:
            session.execute(word_wordList.insert().values(wordList_id=word_list_id, word_id=word_id))
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 单词表删除单词
class DelWordFromWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)
        self.parser.add_argument('word_id', type=int, help='word id', required=True)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['wordList_id']
        word_id = args['word_id']
        try:
            # 判断单词是否在单词表
            word_cnt = session.execute(select([word_wordList]).where(
                and_(
                    word_wordList.c.word_id == word_id,
                    word_wordList.c.wordList_id == word_list_id)
            )).rowcount
            if word_cnt == 0:
                return {'msg': '删除的单词并不在单词表中'}, 400

            session.execute(word_wordList.delete().where(
                and_(
                    word_wordList.c.word_id == word_id,
                    word_wordList.c.wordList_id == word_list_id)
            ))
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 收藏单词表
class LikeWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args["user_id"]
        word_list_id = args["wordList_id"]

        try:
            # 用户不可收藏自己的单词表
            word_list = session.query(WordList).filter(WordList.id == word_list_id).one()
            if word_list.user_id == user_id:
                return {'msg': '你不能收藏自己的单词表'}, 400

            session.execute(user_wordList.insert().values(user_id=user_id, wordList_id=word_list_id))
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 取消收藏单词表
# todo 不可取消未收藏的单词表
class DislikeWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args["user_id"]
        word_list_id = args["wordList_id"]

        try:
            session.execute(user_wordList.delete().where(
                and_(
                    user_wordList.c.user_id == user_id,
                    user_wordList.c.wordList_id == word_list_id)
            ))
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 获取用户收藏单词表
class GetAllUserLikedWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        try:
            user = session.query(User).filter(User.id == user_id).one()
            word_lists = user.liked_word_list
            result = []
            for word_list in word_lists:
                owner = session.query(User).filter(User.id == word_list.user_id).one()
                result_word_list = {
                    'id': word_list.id,
                    'name': word_list.name,
                    'words': [],
                    'image_url': word_list.image_url,
                    'description': word_list.description,
                    'ownerImage_url': owner.image_url,
                    'ownerName': owner.nickname,
                    'user_id': owner.id
                }
                words = word_list.words.all()
                for word in words:
                    result_word_list['words'].append(to_dict(word))
                result.append(result_word_list)
            session.commit()
            return result, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 上传图片到服务器
class PostUserImage(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('image', type=str, help='image', required=True)

    def post(self):
        args = self.parser.parse_args()
        image_str = args['image']
        user_id = args['user_id']
        try:
            path = '//home//images//'
            image = base64.b64decode(image_str)
            image_name = get_time_stamp() + ".jpg"
            print(image_name)
            file = open(path + image_name, 'wb')
            file.write(image)
            file.close()
            # 更新数据库
            user = session.query(User).filter(User.id == user_id).one()
            user.image_url = 'http://47.103.3.131/' + image_name
            session.commit()
            return {'msg': 'success'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 上传词单封面
class PostWordListImage(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)
        self.parser.add_argument('image', type=str, help='image', required=True)

    def post(self):
        args = self.parser.parse_args()
        image_str = args['image']
        word_list_id = args['wordList_id']
        try:
            path = '//home//images//'
            image = base64.b64decode(image_str)
            image_name = get_time_stamp() + ".jpg"
            print(image_name)
            file = open(path + image_name, 'wb')
            file.write(image)
            file.close()
            # 更新数据库
            word_list = session.query(WordList).filter(WordList.id == word_list_id).one()
            word_list.image_url = 'http://47.103.3.131/' + image_name
            session.commit()
            return {'msg': 'success'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 判断用户是否已收藏该词单
class JudgeUserLiked(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)
        self.parser.add_argument('user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        word_list_id = args['wordList_id']
        try:
            liked_word_list_cnt = session.execute(select([user_wordList]).where(
                and_(
                    user_wordList.c.user_id == user_id,
                    user_wordList.c.wordList_id == word_list_id)
            )).rowcount
            session.commit()
            if liked_word_list_cnt == 0:
                return {'msg': False}, 400
            else:
                return {'msg': True}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 按相似度排序
class SortWordsBySimilarity(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('words', action='append')

    def post(self):
        args = self.parser.parse_args()
        words = args['words']

        try:
            words_only_has_name = [eval(word)['name'] for word in words]
            sorted_words = cal_similarity.sort_word_list(words_only_has_name)
            result_json = []
            for word in sorted_words:
                for original_word in words:
                    original_word = eval(original_word)
                    if original_word['name'] == word:
                        result_json.append(
                            {"id": original_word['id'], "name": word,
                             "meaning": original_word['meaning'], "pronounce": original_word['pronounce']})
                        break
            return result_json, 200
        except Exception as e:
            print(e)
            return {'msg': str(e)}, 400


# 自己添加数据用
class BatchAddWordToWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)
        self.parser.add_argument('words', action='append')

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['wordList_id']
        words = args['words']
        try:
            for word in words:
                word_with_id = session.query(Word).filter(Word.name == word).one()
                session.execute(word_wordList.insert().values(wordList_id=word_list_id, word_id=word_with_id.id))
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


class GetSimilarWords(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('word', type=str, help='word', required=True)

    def post(self):
        args = self.parser.parse_args()
        word = args['word'].lower()
        similar_words = cal_similarity.get_most_similar_word(word)
        result_json = []

        try:
            for s_word in similar_words:
                try:
                    db_word = session.query(Word).filter(Word.name == s_word)[0]
                except:
                    continue
                result_json.append(
                    {"id": db_word.id, "name": db_word.name, "meaning": db_word.meaning,
                     "pronounce": db_word.pronounce})
            session.commit()
            return result_json, 200
        except Exception as e:
            print(e)
            session.rollback()
            return result_json, 400


class AddMoment(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('wordList_id', type=int, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['wordList_id']
        user_id = args['user_id']
        try:
            moment = Moment(user_id=user_id, word_list_id=word_list_id)
            session.add(moment)
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


class GetMoment(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        try:
            moments = session.query(Moment).filter(Moment.user_id == user_id) \
                .order_by(Moment.create_time.desc()).limit(10).all()
            result = []
            for moment in moments:
                user = session.query(User).filter(User.id == moment.user_id).one()
                word_list = session.query(WordList).filter(WordList.id == moment.word_list_id).one()
                result_user = {
                    'nickname': user.nickname,
                    'id': user.id,
                    'status': user.status,
                    'image_url': user.image_url
                }

                result_word_list = {
                    'id': word_list.id,
                    'name': word_list.name,
                    'words': [],
                    'image_url': word_list.image_url,
                    'description': word_list.description,
                    'ownerImage_url': user.image_url,
                    'ownerName': user.nickname,
                    'user_id': user.id
                }
                words = word_list.words.all()
                for word in words:
                    result_word_list['words'].append(to_dict(word))

                result_moment = {
                    'wordList': result_word_list,
                    'user': result_user,
                    'create_time': moment.create_time.strftime("%Y-%m-%d %H:%M:%S")
                }

                result.append(result_moment)
            session.commit()
            return result, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


class FollowUser(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('follow_user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        follow_user_id = args['follow_user_id']
        try:
            follow = Follow(user_id=user_id, follow_user_id=follow_user_id)
            session.add(follow)
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


class UnFollowUser(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('follow_user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        follow_user_id = args['follow_user_id']
        try:
            follow = session.query(Follow).filter(Follow.user_id == user_id) \
                .filter(Follow.follow_user_id == follow_user_id).one()
            session.delete(follow)
            session.commit()
            return {'msg': '成功'}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


class GetUserFollowedUser(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        try:
            follows = session.query(Follow).filter(Follow.user_id == user_id)
            result = []
            for follow in follows:
                followed_user = session.query(User).filter(User.id == follow.follow_user_id).one()
                result.append(to_dict(followed_user))
            session.commit()
            return result, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


# 判断用户是否关注该用户
class JudgeIsFollowed(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('follow_user_id', type=int, help='follow user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        follow_user_id = args['follow_user_id']
        try:
            cnt = session.query(Follow).filter(Follow.user_id == user_id,
                                               Follow.follow_user_id == follow_user_id).count()
            session.commit()
            if cnt == 0:
                return {'msg': False}, 400
            else:
                return {'msg': True}, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


class SearchUser(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('search', type=str, help='your search string', required=True)

    def post(self):
        args = self.parser.parse_args()
        search = args['search']
        try:
            users = session.query(User).filter(User.nickname.like('%' + search + '%')).all()
            result = []
            for user in users:
                result.append(to_dict(user))
            session.commit()
            return result, 200
        except Exception as e:
            print(e)
            session.rollback()
            return result, 400


class GetEveryDaySentence(Resource):
    def get(self):
        try:
            r = requests.get('http://api.tecchen.xyz/api/quote/')
            r.encoding = 'utf-8'
            response = json.loads(r.text)
            author = response['data']['author']
            content = response['data']['content']
            translation = response['data']['translation']
            img_url = response['data']['originImgUrls'][0]
            result = {
                'author': author,
                'content': content,
                'translation': translation,
                'img_url': img_url
            }
            return result, 200
        except:
            return {'msg': '失败'}, 400


class GetRecommendWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=str, help='your user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        try:
            word_list_all = []
            follows = session.query(Follow).filter(Follow.user_id == user_id)
            for follow in follows:
                word_list = session.query(WordList).filter(WordList.user_id == follow.follow_user_id).all()
                word_list_all.extend(word_list)
            # 去掉已经收藏的
            for word_list in word_list_all:
                liked_word_list_cnt = session.execute(select([user_wordList]).where(
                    and_(
                        user_wordList.c.user_id == user_id,
                        user_wordList.c.wordList_id == word_list.id)
                )).rowcount
                if liked_word_list_cnt != 0:
                    word_list_all.remove(word_list)
            random.shuffle(word_list_all)
            # 如果还不够
            if len(word_list_all) <= 3:
                db_all_word_list = session.query(WordList).all()
                # 去掉用户自己创建的以及收藏的
                for word_list in db_all_word_list:
                    if word_list.user_id == user_id:
                        db_all_word_list.remove(word_list)
                    liked_word_list_cnt = session.execute(select([user_wordList]).where(
                        and_(
                            user_wordList.c.user_id == user_id,
                            user_wordList.c.wordList_id == word_list.id)
                    )).rowcount
                    if liked_word_list_cnt != 0:
                        db_all_word_list.remove(word_list)
                random.shuffle(db_all_word_list)
                word_list_all.extend(db_all_word_list[:3])
            # 返回
            random.shuffle(word_list_all)
            result = []
            for word_list in word_list_all[:3]:
                user = session.query(User).filter(User.id == word_list.user_id).one()
                result_word_list = {
                    'id': word_list.id,
                    'name': word_list.name,
                    'words': [],
                    'image_url': word_list.image_url,
                    'description': word_list.description,
                    'ownerName': user.nickname,
                    'ownerImage_url': user.image_url,
                    'user_id': user.id
                }
                words = word_list.words.all()
                for word in words:
                    result_word_list['words'].append(to_dict(word))
                result.append(result_word_list)
            session.commit()
            return result, 200
        except Exception as e:
            session.rollback()
            return {'msg': str(e)}, 400


api.add_resource(Register, '/register', methods=['POST'])
api.add_resource(Login, '/login', methods=['POST'])
api.add_resource(GetUserInfoById, '/getUserInfo', methods=['POST'])
api.add_resource(EditUserInfoById, '/editUserInfo', methods=['POST'])

api.add_resource(SearchWord, '/searchWord', methods=['POST'])
api.add_resource(WordDetail, '/wordDetail', methods=['POST'])

api.add_resource(GetAllUserWordListByUserId, '/getAllUserWordList', methods=['POST'])
api.add_resource(AddWordToWordList, '/addWordToWordList', methods=['POST'])
api.add_resource(DelWordFromWordList, '/delWordFromWordList', methods=['POST'])

api.add_resource(AddWordList, '/addWordList', methods=['POST'])
api.add_resource(DelWordListById, '/delWordList', methods=['POST'])
api.add_resource(EditWordListById, '/editWordList', methods=['POST'])
api.add_resource(SearchWordList, '/searchWordList', methods=['POST'])

api.add_resource(GetAllUserLikedWordList, '/getAllUserLikedWordList', methods=['POST'])
api.add_resource(LikeWordList, '/likeWordList', methods=['POST'])
api.add_resource(DislikeWordList, '/dislikeWordList', methods=['POST'])
api.add_resource(JudgeUserLiked, '/judgeUserLiked', methods=['POST'])

api.add_resource(PostUserImage, '/postUserImage', methods=['POST'])
api.add_resource(PostWordListImage, '/postWordListImage', methods=['POST'])

api.add_resource(SortWordsBySimilarity, '/sortWordBySimilarity', methods=['POST'])
api.add_resource(GetSimilarWords, '/getSimilarWords', methods=['POST'])

api.add_resource(AddMoment, '/addMoment', methods=['POST'])
api.add_resource(GetMoment, '/getMoment', methods=['POST'])

api.add_resource(JudgeIsFollowed, '/judgeIsFollowed', methods=['POST'])
api.add_resource(FollowUser, '/followUser', methods=['POST'])
api.add_resource(UnFollowUser, '/unFollowUser', methods=['POST'])
api.add_resource(GetUserFollowedUser, '/getFollowedUser', methods=['POST'])
api.add_resource(SearchUser, '/searchUser', methods=['POST'])

api.add_resource(BatchAddWordToWordList, '/batchAddWordToWordList', methods=['POST'])

api.add_resource(GetEveryDaySentence, '/getEveryDaySentence', methods=['GET'])
api.add_resource(GetRecommendWordList, '/getRecommendWordList', methods=['POST'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
