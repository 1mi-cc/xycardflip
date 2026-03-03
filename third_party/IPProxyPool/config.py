# coding:utf-8
"""IPProxyPool runtime configuration."""

import os
import random

# Keep a small set of reachable proxy feed sources (plain ip:port text).
parserList = [
    {
        "urls": [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=8000&country=all&ssl=all&anonymity=all",
        ],
        "type": "regular",
        "pattern": r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})",
        "position": {"ip": 0, "port": 1, "type": -1, "protocol": -1},
    },
    {
        "urls": [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        ],
        "type": "regular",
        "pattern": r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})",
        "position": {"ip": 0, "port": 1, "type": -1, "protocol": -1},
    },
    {
        "urls": [
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        ],
        "type": "regular",
        "pattern": r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})",
        "position": {"ip": 0, "port": 1, "type": -1, "protocol": -1},
    },
]

DB_CONFIG = {
    "DB_CONNECT_TYPE": "sqlalchemy",
    "DB_CONNECT_STRING": "sqlite:///" + os.path.dirname(__file__) + "/data/proxy.db",
}

CHINA_AREA: list[str] = []
QQWRY_PATH = os.path.dirname(__file__) + "/data/qqwry.dat"
THREADNUM = 5
API_PORT = 8899

UPDATE_TIME = 30 * 60
MINNUM = 20
TIMEOUT = 8
RETRY_TIME = 2

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
]


def get_header() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/plain,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Connection": "keep-alive",
    }


DEFAULT_SCORE = 10

TEST_URL = "http://ip.chinaz.com/getip.aspx"
TEST_IP = "http://httpbin.org/ip"
TEST_HTTP_HEADER = "http://httpbin.org/get"
TEST_HTTPS_HEADER = "https://httpbin.org/get"
CHECK_PROXY = {"function": "baidu_check"}

MAX_CHECK_PROCESS = 2
MAX_CHECK_CONCURRENT_PER_PROCESS = 30
TASK_QUEUE_SIZE = 50
MAX_DOWNLOAD_CONCURRENT = 3
CHECK_WATI_TIME = 1
