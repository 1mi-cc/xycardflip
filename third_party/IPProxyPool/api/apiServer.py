# coding:utf-8
'''
定义几个关键字，count type,protocol,country,area,
'''
import json
import sys
import web
import config
from db.DataStore import sqlhelper
from db.SqlHelper import Proxy

urls = (
    '/', 'select',
    '/delete', 'delete'
)


def start_api_server():
    sys.argv.append('0.0.0.0:%s' % config.API_PORT)
    app = web.application(urls, globals())
    app.run()


class select(object):
    def GET(self):
        inputs = web.input()
        rows = sqlhelper.select(inputs.get('count', None), inputs)
        normalized = []
        for row in rows:
            if isinstance(row, (list, tuple)):
                normalized.append([row[0], row[1], row[2] if len(row) > 2 else None])
                continue
            mapping = getattr(row, "_mapping", None)
            if mapping is not None:
                normalized.append(
                    [
                        mapping.get("ip"),
                        mapping.get("port"),
                        mapping.get("score"),
                    ]
                )
                continue
            try:
                normalized.append([row[0], row[1], row[2] if len(row) > 2 else None])
            except Exception:
                continue
        json_result = json.dumps(normalized, ensure_ascii=False)
        return json_result


class delete(object):
    params = {}

    def GET(self):
        inputs = web.input()
        json_result = json.dumps(sqlhelper.delete(inputs))
        return json_result


if __name__ == '__main__':
    sys.argv.append('0.0.0.0:8000')
    app = web.application(urls, globals())
    app.run()
