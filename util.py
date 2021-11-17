import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime

import urllib3
from dateutil import tz


def get_sign(secret, timestamp):
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return sign


def parse_time(time_str):
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=tz.gettz('Asia/Shanghai'))
    except ValueError:
        return None


def download(item):
    http = urllib3.PoolManager()
    r = http.request('GET', item['href'], preload_content=False)
    data = r.data.decode(encoding='utf-8')
    r.release_conn()
    return data
