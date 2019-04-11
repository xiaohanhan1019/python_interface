import sys
import functools

sys.path.append("..")
sys.path.append("./mdx_resolve")
from mdx_resolve.mdict_query import IndexBuilder
from flask import Flask
from flask_restful import reqparse, abort, Api, Resource

app = Flask(__name__)
api = Api(app)


def cmp_ignore_case(s1, s2):
    s1 = s1.lower()
    s2 = s2.lower()
    if s1 < s2:
        return -1
    elif s1 > s2:
        return 1
    return 0

# 搜索匹配的单词，返回10个
class SearchWord(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('search', type=str, help='your search string', required=True)

    def post(self):
        args = self.parser.parse_args()
        search = args['search']
        print(search)
        builder = IndexBuilder('./mdx_resolve/mdx/Collins.mdx')
        result = sorted(builder.get_mdx_keys(search + "*")[:20], key=functools.cmp_to_key(cmp_ignore_case))
        # todo 优化搜索结果 使其与搜索字符串最匹配

        result_json = [{"name": word_name} for word_name in result]
        return result_json


api.add_resource(SearchWord, '/searchWord', methods=['POST'])

if __name__ == '__main__':
    # app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)
