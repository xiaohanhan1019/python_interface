import sys

sys.path.append("..")
sys.path.append("./mdx_resolve")
from mdx_resolve.mdict_query import IndexBuilder
from flask import Flask
from flask_restful import reqparse, abort, Api, Resource

from sqlalchemy import ForeignKey
import sqlalchemy.orm
import sqlalchemy.ext.declarative

import functools

app = Flask(__name__)
api = Api(app)

engine = sqlalchemy.create_engine("mysql+pymysql://root:SSZZhh~~!!22@47.103.3.131:3306/word_chain", encoding="utf8",
                                  echo=False)
BaseModel = sqlalchemy.ext.declarative.declarative_base()

# 利用Session对象连接数据库
DBSession = sqlalchemy.orm.sessionmaker(bind=engine)
session = DBSession()


class User(BaseModel):
    __tablename__ = 'user'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    account = sqlalchemy.Column("account", sqlalchemy.String(50), nullable=False)
    password = sqlalchemy.Column("password", sqlalchemy.String(50), nullable=False)
    nickname = sqlalchemy.Column("nickname", sqlalchemy.String(50), nullable=False)

    def to_json(self):
        return {
            'id': self.id,
            'account': self.account,
            'nickname': self.nickname
        }


class WordList(BaseModel):
    __tablename__ = 'word_list'

    id = sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True)
    user_id = sqlalchemy.Column("user_id", sqlalchemy.Integer, ForeignKey("user.user_id"), nullable=False)
    name = sqlalchemy.Column("name", sqlalchemy.String(50), nullable=False)


# 按照小写字典序,对搜索结果进行排序
def cmp_ignore_case(s1, s2):
    s1 = s1.lower()
    s2 = s2.lower()
    if s1 < s2:
        return -1
    elif s1 > s2:
        return 1
    return 0


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
        return {'html': result_text[0][:6]+'<meta name="viewport" content="width=device-width,initial-scale=1.0">'+result_text[0][6:], 'css': '<style>'+css+'</style>'}


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
        exist_user = session.query(User).filter(User.account == account)
        try:
            if exist_user.count() == 0:
                session.add(user)
                session.commit()
                return {'message': '注册成功'}
            else:
                return {'message': '用户名已存在'}
        except:
            return {'message': 'system error'}


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
        user = User(account=account, password=password)
        # 判断是否有该用户名
        exist_user = session.query(User).filter(User.account == account)
        if exist_user.count() == 1:
            if user.password == password:
                return {'message': '登陆成功'}
            else:
                return {'message': '密码不正确'}
        else:
            return {'message': '用户不存在'}


# 获取用户信息
class GetUserInfoById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='your user id', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args['id']
        user = session.query(User).filter(User.id == user_id)
        if user.count() == 1:
            return user[0].to_json()
        else:
            return {'message': '用户不存在'}


# 新建单词表
class AddWordList(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='user id', required=True)
        self.parser.add_argument('name', type=str, help='word list name', required=True)

    def post(self):
        args = self.parser.parse_args()
        user_id = args["id"]
        name = args["name"]
        word_list = WordList(user_id=user_id, name=name)
        try:
            session.add(word_list)
            session.commit()
            return {'message': '成功'}
        except:
            return {'message': 'system error'}


# 获取用户所有单词表
class GetAllUserWordListByUserId(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='user id', required=True)

    def post(self):
        args = self.parser.parse_args()


# 获取单词表详情
class GetWordListById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()


# 删除单词表
class DeleteWordListById(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('id', type=int, help='word list id', required=True)

    def post(self):
        args = self.parser.parse_args()


# 单词表添加单词/删除单词


api.add_resource(Register, '/register', methods=['POST'])
api.add_resource(Login, '/login', methods=['POST'])
api.add_resource(GetUserInfoById, '/getUserInfo', methods=['POST'])
api.add_resource(SearchWord, '/searchWord', methods=['POST'])
api.add_resource(WordDetail, '/wordDetail', methods=['POST'])
api.add_resource(AddWordList, '/addWordList', methods=['POST'])

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=5000)
    app.run()
