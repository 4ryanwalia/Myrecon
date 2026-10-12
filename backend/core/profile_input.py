"""Strict local input boundary; never resolve user URLs over the network."""
import re
from urllib.parse import urlsplit
from data.profile_urls import RESERVED_HANDLES, profile_handle
RULES = [{'platform': 'Instagram', 'hosts': ['instagram.com', 'www.instagram.com'], 'host': 'www.instagram.com', 'prefix': '', 'pattern': '[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?'}, {'platform': 'TikTok', 'hosts': ['tiktok.com', 'www.tiktok.com'], 'host': 'www.tiktok.com', 'prefix': '@', 'pattern': '[A-Za-z0-9_][A-Za-z0-9_.]{0,22}[A-Za-z0-9_]|[A-Za-z0-9_]'}, {'platform': 'GitHub', 'hosts': ['github.com', 'www.github.com'], 'host': 'github.com', 'prefix': '', 'pattern': '[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?'}]
RESERVED = RESERVED_HANDLES | set(' about abuse account accounts ads advertise ai api app apps archive article articles auth blog blogs board brand business careers cart categories category challenge channel channels chat checkout cloud codespaces collection collections comment comments community companies company compare contact content cookie cookies copilot corporate courses create creator customer-stories dashboard de developer developers digital direct directory discover docs documentation download downloads edit editor education en enterprise es events explore faq features feed feedback files forum forums fr gallery get gift group groups guide guides hashtag help home hot how i images index info insights install intent invite issues it ja jobs join learn legal library license links list lists live login logout m magazine mail main map maps marketing marketplace media members menu message messages mobile more my new news newsletter notifications oauth offers onboarding opensource order orders organizations orgs p page pages partner partners password payment photo photos plans platform podcast podcasts policies policy post posts premium press pricing privacy product products profile profiles projects pt pulls pulse questions read readme recent redirect reel reels register release releases reset resources results reviews roadmap rss ru s sale search security services session sessions settings share shop shopping showcase signin signup site sitemap solutions source sponsor sponsors start static status store stories story subscribe support tag tags team teams terms test themes topic topics tos tour trending tv u upgrade upload user users video videos view wallet watch web welcome wiki work world write www zh'.split())
def parse_profile_input(value):
    error = "Enter a username or a full supported profile URL; post, video, search and shortened links are not supported."
    if not isinstance(value, str) or len(value) > 8192 or re.search(r"[\x00-\x1f\x7f\\]", value):
        raise ValueError(error)
    value = value.strip()
    if not re.match(r"[a-z][a-z0-9+.-]*:", value, re.I) and '/' not in value:
        handle = value.removeprefix('@')
        if not value.startswith('www.') and re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', handle):
            return {'handle': handle}
        raise ValueError(error)
    u = urlsplit(value)
    rule = next((r for r in RULES if u.hostname in r['hosts']), None)
    if not rule or u.scheme not in ('http','https') or u.username or u.password or u.port or '%' in u.path:
        raise ValueError(error)
    match = re.fullmatch('/' + rule['prefix'] + '(' + rule['pattern'] + ')/?', u.path)
    handle = match[1] if match else ''
    if not handle or handle.lower() in RESERVED or '..' in handle or (rule['platform']=='GitHub' and '--' in handle) or not profile_handle(value):
        raise ValueError(error)
    return {'handle': handle, 'platform': rule['platform'], 'url': 'https://' + rule['host'] + '/' + rule['prefix'] + handle}
