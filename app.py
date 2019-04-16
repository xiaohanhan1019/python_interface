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

    liked_word_list = relationship('WordList',
                                   secondary=user_wordList,
                                   backref=backref('wordList', lazy='dynamic'),
                                   lazy='dynamic'
                                   )


class Word(Base):
    __tablename__ = 'word'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column("name", sqlalchemy.String(50), nullable=False)


class WordList(Base):
    __tablename__ = 'wordList'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    user_id = sqlalchemy.Column("user_id", sqlalchemy.Integer, ForeignKey("user.id"), nullable=False)
    name = sqlalchemy.Column("name", sqlalchemy.String(50), nullable=False)
    create_time = sqlalchemy.Column("create_time", sqlalchemy.DATE, default=datetime.datetime.utcnow())

    # todo 级联删除
    words = relationship('Word',
                         secondary=word_wordList,
                         backref=backref('word', lazy='dynamic', cascade="all,delete"),
                         lazy='dynamic'
                         )


# 按照小写字典序,对搜索结果进行排序
def cmp_ignore_case(s1, s2):
    s1 = s1.lower()
    s2 = s2.lower()
    if s1 < s2:
        return -1
    elif s1 > s2:
        return 1
    return 0


def to_dict(self):
    return {c.name: getattr(self, c.name, None) for c in self.__table__.columns}


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

        result_json = [{"name": word_name} for word_name in result]
        return result_json


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
        user = User(account=account, password=password)
        # 判断是否有该用户名
        exist_user_count = session.query(User).filter(User.account == account).count()
        try:
            if exist_user_count == 0:
                session.add(user)
                session.commit()
                return {'message': '注册成功'}
            else:
                return {'message': '用户名已存在'}
        except Exception as e:
            return {'message': str(e)}


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
            if exist_user.password == password:
                return {'message': '登陆成功'}
            else:
                return {'message': '密码不正确'}
        except Exception as e:
            return {'message': '用户不存在' + str(e)}


# 获取用户信息
class GetUserInfoById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='your user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['id']
        try:
            user = session.query(User).filter(User.id == user_id).one()
            return to_dict(user)
        except Exception as e:
            return {'message': str(e)}


# 新建单词表
class AddWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('name', type=str, help='word list name', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args["user_id"]
        name = args["name"]
        word_list = WordList(user_id=user_id, name=name)
        try:
            session.add(word_list)
            session.commit()
            return {'message': '成功'}
        except Exception as e:
            return {'message': str(e)}


# 删除单词表
# todo 删除单词表只是该单词表不属于该用户，数据需要保存，否则别的用户收藏了就会出问题
class DelWordListById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['id']
        try:
            # todo 不太懂这个级联删除
            session.query(WordList).filter(WordList.id == word_list_id).delete()
            session.commit()
            return {'message': '成功'}
        except Exception as e:
            return {'message': str(e)}


# 获取用户所有单词表
class GetAllUserWordListByUserId(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        word_lists = session.query(WordList).filter(WordList.user_id == user_id).all()
        result = {'word_list': []}
        for word_list in word_lists:
            result_word_list = {
                'name': word_list.name,
                'words': []
            }
            words = word_list.words.all()
            for word in words:
                result_word_list['words'].append(to_dict(word))
            result['word_list'].append(result_word_list)
        return result


# 单词表添加单词
class AddWordToWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='word list id', required=True)
        self.parser.add_argument('word_id', type=int, help='word id', required=True)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['id']
        word_id = args['word_id']
        try:
            session.execute(word_wordList.insert().values(wordList_id=word_list_id, word_id=word_id))
            session.commit()
            return {'message': '成功'}
        except Exception as e:
            return {'message': str(e)}


# 单词表删除单词
class DelWordFromWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='word list id', required=True)
        self.parser.add_argument('word_id', type=int, help='word id', required=True)

    def post(self):
        args = self.parser.parse_args()
        word_list_id = args['id']
        word_id = args['word_id']
        try:
            # 判断单词是否在单词表
            word_cnt = session.execute(select([word_wordList]).where(
                and_(
                    word_wordList.c.word_id == word_id,
                    word_wordList.c.wordList_id == word_list_id)
            )).rowcount
            if word_cnt == 0:
                return {'message': '删除的单词并不在单词表中'}

            session.execute(word_wordList.delete().where(
                and_(
                    word_wordList.c.word_id == word_id,
                    word_wordList.c.wordList_id == word_list_id)
            ))
            session.commit()
            return {'message': '成功'}
        except Exception as e:
            return {'message': str(e)}


# 收藏单词表
class LikedWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('wordList_id', type=str, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args["user_id"]
        word_list_id = args["wordList_id"]

        try:
            # 用户不可收藏自己的单词表
            word_list = session.query(WordList).filter(WordList.id == word_list_id).one()
            if word_list.user_id == user_id:
                return {'message': '你不能收藏自己的单词表'}

            session.execute(user_wordList.insert().values(user_id=user_id, wordList_id=word_list_id))
            session.commit()
            return {'message': '成功'}
        except Exception as e:
            return {'message': str(e)}


# 取消收藏单词表
# todo 不可取消未收藏的单词表
class DislikedWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)
        self.parser.add_argument('wordList_id', type=str, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args["user_id"]
        word_list_id = args["wordList_id"]

        # 不可取消未收藏的单词表

        try:
            session.execute(user_wordList.delete().where(
                and_(
                    user_wordList.c.user_id == user_id,
                    user_wordList.c.wordList_id == word_list_id)
            ))
            session.commit()
            return {'message': '成功'}
        except Exception as e:
            return {'message': str(e)}


# 获取用户收藏单词表
class GetAllUserLikedWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('user_id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['user_id']
        user = session.query(User).filter(User.id == user_id).one()
        word_lists = user.liked_word_list
        result = {'word_list': []}
        for word_list in word_lists:
            result_word_list = {
                'name': word_list.name,
                'words': []
            }
            words = word_list.words.all()
            for word in words:
                result_word_list['words'].append(to_dict(word))
            result['word_list'].append(result_word_list)
        return result


api.add_resource(Register, '/register', methods=['POST'])
api.add_resource(Login, '/login', methods=['POST'])
api.add_resource(GetUserInfoById, '/getUserInfo', methods=['POST'])

api.add_resource(SearchWord, '/searchWord', methods=['POST'])
api.add_resource(WordDetail, '/wordDetail', methods=['POST'])

api.add_resource(GetAllUserWordListByUserId, '/getAllUserWordList', methods=['POST'])
api.add_resource(AddWordToWordList, '/addWordToWordList', methods=['POST'])
api.add_resource(DelWordFromWordList, '/delWordFromWordList', methods=['POST'])
api.add_resource(AddWordList, '/addWordList', methods=['POST'])
api.add_resource(DelWordListById, '/delWordList', methods=['POST'])

api.add_resource(GetAllUserLikedWordList, '/getAllUserLikedWordList', methods=['POST'])
api.add_resource(LikedWordList, '/likedWordList', methods=['POST'])
api.add_resource(DislikedWordList, '/dislikedWordList', methods=['POST'])

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=5000)
    app.run()
