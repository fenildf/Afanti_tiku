#-*-coding:utf8-*-

import sys
import re
import hashlib


def get_md5(url):
    m = hashlib.md5()
    m.update(url)
    return m.hexdigest()

def extract_num(text):
    match_re = re.match(".*?(\d+).*",text)
    if match_re:
        nums = int(match_re.group(1))
    else:
        nums = 0

if __name__ == '__main__':
    #hashlib函数不接收Unicode编码，必须转换成utf-8模式
    print(get_md5("http://www.wanfangdata.com.cn/"))
