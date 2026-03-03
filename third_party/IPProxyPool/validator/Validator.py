# coding:utf-8

import json
import os
import queue as queue_lib
import sys
import time
from multiprocessing import Process, Queue

import chardet
import psutil
import requests

import config
from db.DataStore import sqlhelper
from util.exception import Test_URL_Fail


def detect_from_db(myip, proxy, proxies_set):
    proxy_dict = {'ip': proxy[0], 'port': proxy[1]}
    result = detect_proxy(myip, proxy_dict)
    if result:
        proxy_str = '%s:%s' % (proxy[0], proxy[1])
        proxies_set.add(proxy_str)
        return

    if proxy[2] < 1:
        sqlhelper.delete({'ip': proxy[0], 'port': proxy[1]})
        return

    score = proxy[2] - 1
    sqlhelper.update({'ip': proxy[0], 'port': proxy[1]}, {'score': score})
    proxy_str = '%s:%s' % (proxy[0], proxy[1])
    proxies_set.add(proxy_str)


def _start_batch(tasklist, myip, queue2, cntl_q, proc_pool):
    if not tasklist:
        return []
    p = Process(target=process_start, args=(tasklist, myip, queue2, cntl_q))
    p.start()
    proc_pool[p.pid] = p
    return []


def validator(queue1, queue2, myip):
    tasklist = []
    proc_pool = {}
    cntl_q = Queue()

    while True:
        # Reap finished child workers.
        if not cntl_q.empty():
            try:
                pid = cntl_q.get()
                proc = proc_pool.pop(pid, None)
                if proc is not None and proc.is_alive():
                    proc_ps = psutil.Process(pid)
                    proc_ps.kill()
                    proc_ps.wait(timeout=2)
            except Exception:
                pass

        if len(proc_pool) >= config.MAX_CHECK_PROCESS:
            time.sleep(config.CHECK_WATI_TIME)
            continue

        try:
            proxy = queue1.get(timeout=1)
            tasklist.append(proxy)
            if len(tasklist) >= config.MAX_CHECK_CONCURRENT_PER_PROCESS:
                tasklist = _start_batch(tasklist, myip, queue2, cntl_q, proc_pool)
        except queue_lib.Empty:
            # Flush partial batch instead of waiting forever.
            if tasklist:
                tasklist = _start_batch(tasklist, myip, queue2, cntl_q, proc_pool)
        except Exception:
            if tasklist:
                tasklist = _start_batch(tasklist, myip, queue2, cntl_q, proc_pool)


def process_start(tasks, myip, queue2, cntl):
    for task in tasks:
        try:
            detect_proxy(myip, task, queue2)
        except Exception:
            continue
    cntl.put(os.getpid())


def detect_proxy(selfip, proxy, queue2=None):
    ip = proxy['ip']
    port = proxy['port']
    proxies = {"http": "http://%s:%s" % (ip, port), "https": "http://%s:%s" % (ip, port)}
    protocol, types, speed = getattr(sys.modules[__name__], config.CHECK_PROXY['function'])(selfip, proxies)
    if protocol >= 0:
        proxy['protocol'] = protocol
        proxy['types'] = types
        proxy['speed'] = speed
    else:
        proxy = None
    if queue2:
        queue2.put(proxy)
    return proxy


def checkProxy(selfip, proxies):
    protocol = -1
    types = -1
    speed = -1
    http, http_types, http_speed = _checkHttpProxy(selfip, proxies)
    https, https_types, https_speed = _checkHttpProxy(selfip, proxies, False)
    if http and https:
        protocol = 2
        types = http_types
        speed = http_speed
    elif http:
        types = http_types
        protocol = 0
        speed = http_speed
    elif https:
        types = https_types
        protocol = 1
        speed = https_speed
    return protocol, types, speed


def _checkHttpProxy(selfip, proxies, isHttp=True):
    types = -1
    speed = -1
    test_url = config.TEST_HTTP_HEADER if isHttp else config.TEST_HTTPS_HEADER
    try:
        start = time.time()
        with requests.Session() as session:
            session.trust_env = False
            r = session.get(url=test_url, headers=config.get_header(), timeout=config.TIMEOUT, proxies=proxies)
        if r.ok:
            speed = round(time.time() - start, 2)
            content = json.loads(r.text)
            headers = content.get('headers', {})
            ip = content.get('origin', '')
            proxy_connection = headers.get('Proxy-Connection', None)
            if isinstance(ip, str) and ',' in ip:
                types = 2
            elif proxy_connection:
                types = 1
            else:
                types = 0
            return True, types, speed
        return False, types, speed
    except Exception:
        return False, types, speed


def baidu_check(selfip, proxies):
    protocol = -1
    types = -1
    speed = -1
    try:
        start = time.time()
        with requests.Session() as session:
            session.trust_env = False
            r = session.get(url='https://www.baidu.com', headers=config.get_header(), timeout=config.TIMEOUT, proxies=proxies)
        r.encoding = chardet.detect(r.content).get('encoding') or 'utf-8'
        if r.ok:
            speed = round(time.time() - start, 2)
            protocol = 0
            types = 0
    except Exception:
        protocol = -1
        types = -1
        speed = -1
    return protocol, types, speed


def getMyIP():
    try:
        with requests.Session() as session:
            session.trust_env = False
            r = session.get(url=config.TEST_IP, headers=config.get_header(), timeout=config.TIMEOUT)
        ip = json.loads(r.text)
        value = str(ip.get('origin') or '').strip()
        if value:
            return value
    except Exception:
        pass
    # Fallback to a harmless local marker instead of aborting startup.
    return '127.0.0.1'


if __name__ == '__main__':
    ip = '222.186.161.132'
    port = 3128
    proxies = {"http": "http://%s:%s" % (ip, port), "https": "http://%s:%s" % (ip, port)}
    _checkHttpProxy(None, proxies)
