# coding:utf-8

import ipaddress
import re

from lxml import etree

from config import QQWRY_PATH
from util.IPAddress import IPAddresss


class Html_Parser(object):
    def __init__(self):
        self.ips = IPAddresss(QQWRY_PATH)

    def parse(self, response, parser):
        parser_type = str(parser.get('type') or '').strip().lower()
        if parser_type == 'xpath':
            return self.XpathPraser(response, parser)
        if parser_type == 'regular':
            return self.RegularPraser(response, parser)
        if parser_type == 'module':
            fn = getattr(self, parser.get('moduleName', ''), None)
            return fn(response, parser) if callable(fn) else None
        return None

    @staticmethod
    def _safe_port(value):
        try:
            p = int(str(value).strip())
        except Exception:
            return None
        if 1 <= p <= 65535:
            return p
        return None

    @staticmethod
    def _safe_ip(value):
        text = str(value or '').strip()
        if not text:
            return ''
        try:
            ipaddress.ip_address(text)
            return text
        except Exception:
            return ''

    def _build_proxy(self, ip, port):
        if not ip or port is None:
            return None
        country = ''
        area = ''
        try:
            addr = self.ips.getIpAddr(self.ips.str2ip(ip))
            if isinstance(addr, str):
                area = addr
        except Exception:
            area = ''

        return {
            'ip': ip,
            'port': int(port),
            'types': 0,
            'protocol': 0,
            'country': country,
            'area': area,
            'speed': 100,
        }

    def XpathPraser(self, response, parser):
        proxylist = []
        root = etree.HTML(response)
        if root is None:
            return proxylist
        proxys = root.xpath(parser['pattern'])
        for proxy in proxys:
            try:
                ip_node = proxy.xpath(parser['position']['ip'])
                port_node = proxy.xpath(parser['position']['port'])
                ip_raw = ip_node[0].text if ip_node else ''
                port_raw = port_node[0].text if port_node else ''
                ip = self._safe_ip(ip_raw)
                port = self._safe_port(port_raw)
                built = self._build_proxy(ip, port)
                if built:
                    proxylist.append(built)
            except Exception:
                continue
        return proxylist

    def RegularPraser(self, response, parser):
        proxylist = []
        pattern = re.compile(parser['pattern'])
        matches = pattern.findall(response)
        if not matches:
            return proxylist

        ip_idx = int(parser['position'].get('ip', 0))
        port_idx = int(parser['position'].get('port', 1))
        for match in matches:
            try:
                if isinstance(match, (tuple, list)):
                    ip_raw = match[ip_idx]
                    port_raw = match[port_idx]
                else:
                    # Single capture fallback: "ip:port"
                    parts = str(match).split(':', 1)
                    if len(parts) != 2:
                        continue
                    ip_raw, port_raw = parts[0], parts[1]
                ip = self._safe_ip(ip_raw)
                port = self._safe_port(port_raw)
                built = self._build_proxy(ip, port)
                if built:
                    proxylist.append(built)
            except Exception:
                continue
        return proxylist

    # Backward compatibility for old module parser names.
    def CnproxyPraser(self, response, parser):
        return self.RegularPraser(response, parser)

    def proxy_listPraser(self, response, parser):
        return self.RegularPraser(response, parser)
