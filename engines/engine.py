import hashlib
import multiprocessing
import re
import threading

import sys
from collections import Counter
import random

import dns
import time
import json
from engines.enumarator_base import EnumeratorBase
import requests

# Python 2.x and 3.x compatiablity
from util.logger import Logger

if sys.version > '3':
    import urllib.parse as urlparse
    import urllib.parse as urllib
else:
    import urlparse
    import urllib


class EnumratorBaseThreaded(multiprocessing.Process, EnumeratorBase):
    def __init__(self, base_url, engine_name, domain, subdomains=None, q=None, lock=threading.Lock(),
                 silent=False, logger=None):
        subdomains = subdomains or []
        EnumeratorBase.__init__(self, base_url, engine_name, domain, subdomains, silent, logger)
        multiprocessing.Process.__init__(self)
        self.lock = lock
        self.logger = logger
        self.q = q
        return

    def run(self):
        domain_list = self.enumerate()
        for domain in domain_list:
            self.q.append(domain)


class GoogleEnum(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = "https://google.com/search?q={query}&btnG=Search&hl=en-US&biw=&bih=&gbv=1&start={page_no}&filter=0"
        self.engine_name = "Google"
        self.MAX_DOMAINS = 11
        self.MAX_PAGES = 200
        super(GoogleEnum, self).__init__(base_url, self.engine_name, domain, subdomains, silent=silent, logger=logger)
        self.q = q
        return

    def extract_domains(self, resp):
        link_regx = re.compile('<cite.*?>(.*?)</cite>')
        try:
            links_list = link_regx.findall(resp)
            for link in links_list:
                link = re.sub('<span.*>', '', link)
                if not link.startswith('http'):
                    link = "http://" + link
                subdomain = urlparse.urlparse(link).netloc
                if subdomain and subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception:
            pass
        return links_list

    def check_response_errors(self, resp):
        if type(resp) == type(1):
            return False
        if 'Our systems have detected unusual traffic' in resp:
            self.print_(self.logger.R + "[!] Error: Google probably now is blocking our requests" + self.logger.W)
            self.print_(self.logger.R + "[~] Finished now the Google Enumeration ..." + self.logger.W)
            return False
        return True

    def should_sleep(self):
        time.sleep(5)
        return

    def generate_query(self):
        if self.subdomains:
            fmt = 'site:{domain} -www.{domain} -{found}'
            found = ' -'.join(self.subdomains[:self.MAX_DOMAINS - 2])
            query = fmt.format(domain=self.domain, found=found)
        else:
            query = "site:{domain} -www.{domain}".format(domain=self.domain)
        return query


class YahooEnum(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = "https://search.yahoo.com/search?p={query}&b={page_no}"
        self.engine_name = "Yahoo"
        self.MAX_DOMAINS = 10
        self.MAX_PAGES = 0
        super(YahooEnum, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                        logger=logger)
        self.q = q
        return

    def extract_domains(self, resp):
        link_regx2 = re.compile('<span class=" fz-.*? fw-m fc-12th wr-bw.*?">(.*?)</span>')
        link_regx = re.compile('<span class="txt"><span class=" cite fw-xl fz-15px">(.*?)</span>')
        links_list = []
        try:
            links = link_regx.findall(resp)
            links2 = link_regx2.findall(resp)
            links_list = links + links2
            for link in links_list:
                link = re.sub("<(\/)?b>", "", link)
                if not link.startswith('http'):
                    link = "http://" + link
                subdomain = urlparse.urlparse(link).netloc
                if not subdomain.endswith(self.domain):
                    continue
                if subdomain and subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception:
            pass

        return links_list

    def should_sleep(self):
        return

    def get_page(self, num):
        return num + 10

    def generate_query(self):
        if self.subdomains:
            fmt = 'site:{domain} -domain:www.{domain} -domain:{found}'
            found = ' -domain:'.join(self.subdomains[:77])
            query = fmt.format(domain=self.domain, found=found)
        else:
            query = "site:{domain}".format(domain=self.domain)
        return query


class AskEnum(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'http://www.ask.com/web?q={query}&page={page_no}&qid=8D6EE6BF52E0C04527E51F64F22C4534&o=0&l=dir&qsrc=998&qo=pagination'
        self.engine_name = "Ask"
        self.MAX_DOMAINS = 11
        self.MAX_PAGES = 0

        super(AskEnum, self).__init__(base_url, self.engine_name, domain, subdomains, silent=silent,
                                         logger=logger)
        self.q = q
        return

    def extract_domains(self, resp):
        link_regx = re.compile('<p class="web-result-url">(.*?)</p>')
        try:
            links_list = []
            links_list = link_regx.findall(resp)
            for link in links_list:
                if not link.startswith('http'):
                    link = "http://" + link
                subdomain = urlparse.urlparse(link).netloc
                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception:
            pass

        return links_list

    def get_page(self, num):
        return num + 1

    def generate_query(self):
        if self.subdomains:
            fmt = 'site:{domain} -www.{domain} -{found}'
            found = ' -'.join(self.subdomains[:self.MAX_DOMAINS])
            query = fmt.format(domain=self.domain, found=found)
        else:
            query = "site:{domain} -www.{domain}".format(domain=self.domain)

        return query


class BingEnum(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://www.bing.com/search?q={query}&go=Submit&first={page_no}'
        self.engine_name = "Bing"
        self.MAX_DOMAINS = 30
        self.MAX_PAGES = 0
        super(BingEnum, self).__init__(base_url, self.engine_name, domain, subdomains, silent=silent,
                                         logger=logger)
        self.q = q
        return

    def extract_domains(self, resp):
        link_regx = re.compile('<li class="b_algo"><h2><a href="(.*?)"')
        link_regx2 = re.compile('<div class="b_title"><h2><a href="(.*?)"')
        try:
            links = link_regx.findall(resp)
            links2 = link_regx2.findall(resp)
            links_list = links + links2

            for link in links_list:
                link = re.sub('<(\/)?strong>|<span.*?>|<|>', '', link)
                if not link.startswith('http'):
                    link = "http://" + link
                subdomain = urlparse.urlparse(link).netloc
                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception:
            pass

        return links_list

    def generate_query(self):
        if self.subdomains:
            fmt = 'domain:{domain} -www.{domain} -{found}'
            found = ' -'.join(self.subdomains[:self.MAX_DOMAINS])
            query = fmt.format(domain=self.domain, found=found)
        else:
            query = "domain:{domain} -www.{domain}".format(domain=self.domain)
        return query


class BaiduEnum(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://www.baidu.com/s?pn={page_no}&wd={query}&oq={query}'
        self.engine_name = "Baidu"
        self.MAX_DOMAINS = 2
        self.MAX_PAGES = 760
        super(BaiduEnum, self).__init__(base_url, self.engine_name, domain, subdomains, silent=silent,
                                         logger=logger)
        self.querydomain = self.domain
        self.q = q
        return

    def extract_domains(self, resp):
        found_newdomain = False
        subdomain_list = []
        link_regx = re.compile('<a.*?class="c-showurl".*?>(.*?)</a>')
        try:
            links = link_regx.findall(resp)
            for link in links:
                link = re.sub('<.*?>|>|<|&nbsp;', '', link)
                if not link.startswith('http'):
                    link = "http://" + link
                subdomain = urlparse.urlparse(link).netloc
                if subdomain.endswith(self.domain):
                    subdomain_list.append(subdomain)
                    if subdomain not in self.subdomains and subdomain != self.domain:
                        found_newdomain = True
                        if self.logger.is_verbose:
                            self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                        self.subdomains.append(subdomain.strip())
        except Exception:
            pass
        if not found_newdomain and subdomain_list:
            self.querydomain = self.findsubs(subdomain_list)
        return links

    def findsubs(self, subdomains):
        count = Counter(subdomains)
        subdomain1 = max(count, key=count.get)
        count.pop(subdomain1, "None")
        subdomain2 = max(count, key=count.get) if count else ''
        return (subdomain1, subdomain2)

    def check_response_errors(self, resp):
        return True

    def should_sleep(self):
        time.sleep(random.randint(2, 5))
        return

    def generate_query(self):
        if self.subdomains and self.querydomain != self.domain:
            found = ' -site:'.join(self.querydomain)
            query = "site:{domain} -site:www.{domain} -site:{found} ".format(domain=self.domain, found=found)
        else:
            query = "site:{domain} -site:www.{domain}".format(domain=self.domain)
        return query


class NetcraftEnum(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        self.base_url = 'https://searchdns.netcraft.com/?restriction=site+ends+with&host={domain}'
        self.engine_name = "Netcraft"
        self.lock = threading.Lock()
        super(NetcraftEnum, self).__init__(self.base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                           logger=logger)
        self.q = q
        return

    def req(self, url, cookies=None):
        cookies = cookies or {}
        try:
            resp = self.session.get(url, headers=self.headers, timeout=self.timeout, cookies=cookies)
        except Exception as e:
            self.print_(e, 'netcraft modules')
            resp = None
        return resp

    def get_next(self, resp):
        link_regx = re.compile('<A href="(.*?)"><b>Next page</b></a>')
        link = link_regx.findall(resp)
        link = re.sub('host=.*?%s' % self.domain, 'host=%s' % self.domain, link[0])
        url = 'http://searchdns.netcraft.com' + link
        return url

    def create_cookies(self, cookie):
        cookies = dict()
        cookies_list = cookie[0:cookie.find(';')].split("=")
        cookies[cookies_list[0]] = cookies_list[1]
        cookies['netcraft_js_verification_response'] = hashlib.sha1(urllib.unquote(cookies_list[1]).encode('utf-8')).hexdigest()
        return cookies

    def get_cookies(self, headers):
        if 'set-cookie' in headers:
            cookies = self.create_cookies(headers['set-cookie'])
        else:
            cookies = {}
        return cookies

    def enumerate(self):
        start_url = self.base_url.format(domain='example.com')
        resp = self.req(start_url)
        cookies = self.get_cookies(resp.headers)
        url = self.base_url.format(domain=self.domain)
        while True:
            resp = self.get_response(self.req(url, cookies))
            self.extract_domains(resp)
            if 'Next page' not in resp:
                return self.subdomains
                break
            url = self.get_next(resp)

    def extract_domains(self, resp):
        link_regx = re.compile('<a href="http://toolbar.netcraft.com/site_report\?url=(.*)">')
        try:
            links_list = link_regx.findall(resp)
            for link in links_list:
                subdomain = urlparse.urlparse(link).netloc
                if not subdomain.endswith(self.domain):
                    continue
                if subdomain and subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception:
            pass
        return links_list


class DNSdumpster(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://dnsdumpster.com/'
        self.live_subdomains = []
        self.engine_name = "DNSdumpster"
        self.threads = 70
        self.lock = threading.BoundedSemaphore(value=self.threads)
        self.q = q
        super(DNSdumpster, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                          logger=logger)
        return

    def check_host(self, host):
        is_valid = False
        Resolver = dns.resolver.Resolver()
        Resolver.nameservers = ['8.8.8.8', '8.8.4.4']
        self.lock.acquire()
        try:
            ip = Resolver.query(host, 'A')[0].to_text()
            if ip:
                if self.logger.is_verbose:
                    self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, host))
                is_valid = True
                self.live_subdomains.append(host)
        except:
            pass
        self.lock.release()
        return is_valid

    def req(self, req_method, url, params=None):
        params = params or {}
        headers = dict(self.headers)
        headers['Referer'] = 'https://dnsdumpster.com'
        try:
            if req_method == 'GET':
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
            else:
                resp = self.session.post(url, data=params, headers=headers, timeout=self.timeout)
        except Exception as e:
            self.print_(e)
            resp = None
        return self.get_response(resp)

    def get_csrftoken(self, resp):
        csrf_regex = re.compile("<input type='hidden' name='csrfmiddlewaretoken' value='(.*?)' />", re.S)
        token = csrf_regex.findall(resp)[0]
        return token.strip()

    def enumerate(self, **kwargs):
        resp = self.req('GET', self.base_url)
        token = self.get_csrftoken(resp)
        params = {'csrfmiddlewaretoken': token, 'targetip': self.domain}
        post_resp = self.req('POST', self.base_url, params)
        self.extract_domains(post_resp)
        for subdomain in self.subdomains:
            t = threading.Thread(target=self.check_host, args=(subdomain,))
            t.start()
            t.join()
        return self.live_subdomains

    def extract_domains(self, resp):
        tbl_regex = re.compile('<a name="hostanchor"><\/a>Host Records.*?<table.*?>(.*?)</table>', re.S)
        link_regex = re.compile('<td class="col-md-4">(.*?)<br>', re.S)
        links = []
        try:
            results_tbl = tbl_regex.findall(resp)[0]
        except IndexError:
            results_tbl = ''
        links_list = link_regex.findall(results_tbl)
        links = list(set(links_list))
        for link in links:
            subdomain = link.strip()
            if not subdomain.endswith(self.domain):
                continue
            if subdomain and subdomain not in self.subdomains and subdomain != self.domain:
                self.subdomains.append(subdomain.strip())
        return links


class Virustotal(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://www.virustotal.com/en/domain/{domain}/information/'
        self.engine_name = "Virustotal"
        self.lock = threading.Lock()
        self.q = q
        super(Virustotal, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                         logger=logger)
        return

    # the main send_req need to be rewritten
    def send_req(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=self.timeout)
        except Exception as e:
            self.print_(e)
            resp = None

        return self.get_response(resp)

    # once the send_req is rewritten we don't need to call this function, the stock one should be ok
    def enumerate(self):
        url = self.base_url.format(domain=self.domain)
        resp = self.send_req(url)
        self.extract_domains(resp)
        return self.subdomains

    def extract_domains(self, resp):
        link_regx = re.compile('<div class="enum.*?">.*?<a target="_blank" href=".*?">(.*?)</a>', re.S)
        try:
            links = link_regx.findall(resp)
            for link in links:
                subdomain = link.strip()
                if not subdomain.endswith(self.domain):
                    continue
                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception:
            pass


class ThreatCrowd(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://www.threatcrowd.org/searchApi/v2/domain/report/?domain={domain}'
        self.engine_name = "ThreatCrowd"
        self.lock = threading.Lock()
        self.q = q
        super(ThreatCrowd, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                          logger=logger)
        return

    def req(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=self.timeout)
        except Exception:
            resp = None

        return self.get_response(resp)

    def enumerate(self):
        url = self.base_url.format(domain=self.domain)
        resp = self.req(url)
        self.extract_domains(resp)
        return self.subdomains

    def extract_domains(self, resp):
        try:
            links = json.loads(resp)['subdomains']
            for link in links:
                subdomain = link.strip()
                if not subdomain.endswith(self.domain):
                    continue
                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception as e:
            pass


class CrtSearch(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://crt.sh/?q=%25.{domain}'
        self.engine_name = "SSL Certificates"
        self.lock = threading.Lock()
        self.q = q
        super(CrtSearch, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                        logger=logger)
        return

    def req(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=self.timeout)
        except Exception:
            resp = None

        return self.get_response(resp)

    def enumerate(self):
        url = self.base_url.format(domain=self.domain)
        resp = self.req(url)
        if resp:
            self.extract_domains(resp)
        return self.subdomains

    def extract_domains(self, resp):
        link_regx = re.compile('<TD>(.*?)</TD>')
        try:
            links = link_regx.findall(resp)
            for link in links:
                subdomain = link.strip()
                if not subdomain.endswith(self.domain) or '*' in subdomain:
                    continue

                if '@' in subdomain:
                    subdomain = subdomain[subdomain.find('@') + 1:]

                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.logger.is_verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception as e:
            pass


class PassiveDNS(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://api.sublist3r.com/search.php?domain={domain}'
        self.engine_name = "PassiveDNS"
        self.lock = threading.Lock()
        self.q = q
        super(PassiveDNS, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                         logger=logger)
        return

    def req(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=self.timeout)
        except Exception as e:
            resp = None

        return self.get_response(resp)

    def enumerate(self):
        url = self.base_url.format(domain=self.domain)
        resp = self.req(url)
        if not resp:
            return self.subdomains

        self.extract_domains(resp)
        return self.subdomains

    def extract_domains(self, resp):
        try:
            subdomains = json.loads(resp)
            for subdomain in subdomains:
                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception as e:
            pass


class HackerTarget(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://api.hackertarget.com/hostsearch/?q={domain}'
        self.engine_name = "HackerTarget"
        self.lock = threading.Lock()
        self.q = q
        super(HackerTarget, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                           logger=logger)
        return

    def req(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=self.timeout)
        except Exception as e:
            resp = None

        return self.get_response(resp)

    def enumerate(self):
        url = self.base_url.format(domain=self.domain)
        resp = self.req(url)
        if not resp:
            return self.subdomains

        self.extract_domains(resp)
        return self.subdomains

    def extract_domains(self, resp):
        try:
            for subdomain in resp.split('\n'):
                subdomain = subdomain.split(',')[0]
                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception as e:
            pass


class DnsDB(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://www.dnsdb.org/f/{domain}.dnsdb.org/'
        self.engine_name = "DnsDB"
        self.lock = threading.Lock()
        self.q = q
        super(DnsDB, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent, logger=logger)
        return

    def req(self, url):
        try:
            resp = self.session.get(url, headers=self.headers, timeout=self.timeout)
        except Exception as e:
            resp = None

        return self.get_response(resp)

    def enumerate(self):
        url = self.base_url.format(domain=self.domain)
        resp = self.req(url)
        if not resp:
            return self.subdomains

        self.extract_domains(resp)
        return self.subdomains

    def extract_domains(self, resp):
        try:
            subdomains = re.findall(r"(?<=href=\").+?(?=\")|(?<=href=\').+?(?=\')", resp)
            for subdomain in subdomains:
                subdomain = subdomain.replace('https://', '').replace('.dnsdb.org/', '')
                if subdomain not in self.subdomains and subdomain != self.domain:
                    if self.verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
        except Exception as e:
            pass


class GoogleTER(EnumratorBaseThreaded):
    def __init__(self, domain, subdomains=None, q=None, silent=False, logger=None):
        subdomains = subdomains or []
        base_url = 'https://www.google.com/transparencyreport/jsonp/ct/search?domain= \
                   {domain}&incl_exp=false&incl_sub=true&c='
        self.engine_name = "GoogleTER"
        self.lock = threading.Lock()
        self.q = q
        self.Token = ""
        super(GoogleTER, self).__init__(base_url, self.engine_name, domain, subdomains, q=q, silent=silent,
                                        logger=logger)
        return

    def req(self, url):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 \
                          Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
        }

        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
        except Exception as e:
            self.print_(e)
            resp = None
        return self.get_response(resp)

    def enumerate(self):
        url = self.base_url.format(domain=self.domain)
        while True:
            resp = self.req(url)
            if not type(resp) == type(1):
                self.extract_domains(resp)
                if "nextPageToken" not in resp:
                    return self.subdomains
                url = self.base_url.format(domain=self.domain) + "&token=" + self.Token.replace("=", "%3D")

    def extract_domains(self, resp):
        _jsonp_begin = r'/* API response */('
        _jsonp_end = r'));'
        try:

            googleresult = json.loads(resp[len(_jsonp_begin):-len(_jsonp_end)])
            for subs in googleresult["results"]:

                if self.domain in googleresult:
                    continue
                subdomain = subs["subject"]
                if subdomain.startswith("*."):
                    subdomain = subdomain.replace("*.", "")
                if subdomain not in self.subdomains and subdomain != self.domain and subdomain.endswith(self.domain):
                    if self.verbose:
                        self.print_("%s%s: %s%s" % (self.logger.R, self.engine_name, self.logger.W, subdomain))
                    self.subdomains.append(subdomain.strip())
            self.Token = googleresult["nextPageToken"]
        except Exception:
            pass


class Engines:
    supported_engines = {'baidu': BaiduEnum,
                         'yahoo': YahooEnum,
                         'google': GoogleEnum,
                         'bing': BingEnum,
                         'ask': AskEnum,
                         'netcraft': NetcraftEnum,
                         'dnsdumpster': DNSdumpster,
                         'virustotal': Virustotal,
                         'threatcrowd': ThreatCrowd,
                         'ssl': CrtSearch,
                         'passivedns': PassiveDNS,
                         'googleter': GoogleTER,
                         'hackertarget': HackerTarget,
                         'dnsdb': DnsDB
                         }
