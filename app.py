import sys

sys.path.append("..")
sys.path.append("./mdx_resolve")
from mdx_resolve.mdict_query import IndexBuilder
from flask import Flask
from flask_restful import reqparse, abort, Api, Resource

app = Flask(__name__)
api = Api(app)


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
        result = builder.get_mdx_keys("*" + search + "*")[:10]
        # todo 优化搜索结果 使其与搜索字符串最匹配

        result_json = [{"name": word_name} for word_name in result]
        return result_json


api.add_resource(SearchWord, '/searchWord', methods=['POST'])

if __name__ == '__main__':
    app.run(debug=True)
