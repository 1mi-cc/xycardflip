# coding:utf-8

import sys
import time

from config import MINNUM, UPDATE_TIME, parserList
from db.DataStore import sqlhelper
from spider.HtmlDownloader import Html_Downloader
from spider.HtmlPraser import Html_Parser
from validator.Validator import detect_from_db


def startProxyCrawl(queue, db_proxy_num, myip):
    crawl = ProxyCrawl(queue, db_proxy_num, myip)
    crawl.run()


class ProxyCrawl(object):
    proxies = set()

    def __init__(self, queue, db_proxy_num, myip):
        self.queue = queue
        self.db_proxy_num = db_proxy_num
        self.myip = myip

    def run(self):
        while True:
            self.proxies.clear()
            sys.stdout.write('IPProxyPool----->>>>>>>>beginning\r\n')
            sys.stdout.flush()

            proxylist = sqlhelper.select()
            for proxy in proxylist:
                try:
                    detect_from_db(self.myip, proxy, self.proxies)
                except Exception:
                    continue

            self.db_proxy_num.value = len(self.proxies)
            msg = 'IPProxyPool----->>>>>>>>db exists ip:%d' % len(self.proxies)

            if len(self.proxies) < MINNUM:
                msg += '\r\nIPProxyPool----->>>>>>>>now ip num < MINNUM,start crawling...'
                sys.stdout.write(msg + "\r\n")
                sys.stdout.flush()
                for parser in parserList:
                    try:
                        self.crawl(parser)
                    except Exception:
                        continue
            else:
                msg += '\r\nIPProxyPool----->>>>>>>>now ip num meet the requirement,wait UPDATE_TIME...'
                sys.stdout.write(msg + "\r\n")
                sys.stdout.flush()

            time.sleep(UPDATE_TIME)

    def crawl(self, parser):
        html_parser = Html_Parser()
        for url in parser.get('urls', []):
            response = Html_Downloader.download(url)
            if response is None:
                continue
            proxylist = html_parser.parse(response, parser)
            if not proxylist:
                continue
            for proxy in proxylist:
                proxy_str = '%s:%s' % (proxy['ip'], proxy['port'])
                if proxy_str in self.proxies:
                    continue
                self.proxies.add(proxy_str)
                while self.queue.full():
                    time.sleep(0.1)
                self.queue.put(proxy)
