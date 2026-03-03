# coding:utf-8

import random

import chardet
import requests

import config
from db.DataStore import sqlhelper


class Html_Downloader(object):
    @staticmethod
    def download(url):
        try:
            with requests.Session() as session:
                session.trust_env = False
                r = session.get(url=url, headers=config.get_header(), timeout=config.TIMEOUT)
            r.encoding = chardet.detect(r.content).get('encoding') or 'utf-8'
            if (not r.ok) or len(r.content) < 20:
                raise ConnectionError
            return r.text
        except Exception:
            count = 0
            proxylist = sqlhelper.select(10)
            if not proxylist:
                return None

            while count < config.RETRY_TIME:
                try:
                    proxy = random.choice(proxylist)
                    ip = proxy[0]
                    port = proxy[1]
                    proxies = {
                        "http": "http://%s:%s" % (ip, port),
                        "https": "http://%s:%s" % (ip, port),
                    }
                    with requests.Session() as session:
                        session.trust_env = False
                        r = session.get(
                            url=url,
                            headers=config.get_header(),
                            timeout=config.TIMEOUT,
                            proxies=proxies,
                        )
                    r.encoding = chardet.detect(r.content).get('encoding') or 'utf-8'
                    if (not r.ok) or len(r.content) < 20:
                        raise ConnectionError
                    return r.text
                except Exception:
                    count += 1

        return None
