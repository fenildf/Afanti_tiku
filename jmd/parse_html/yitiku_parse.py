# -*- coding: utf-8 -*-
import traceback
import json
from jmd import jmd
import pymysql
import pymysql.cursors
from question_template import Question,QuestionFormatter
from multiprocessing import Pool, Process
import re
import time
from w3lib.html import remove_tags
from twisted.enterprise import adbapi
import os
from afanti_tiku_lib.html.image_magic import ImageMagic
from afanti_tiku_lib.html.magic import HtmlMagic
import datetime
import logging

LOGGING_FORMAT = '%(asctime)-15s:%(levelname)s: %(message)s'
logging.basicConfig(format=LOGGING_FORMAT, level=logging.INFO,
                    filename='working/yitiku_parse.log', filemode='a')

_DIR = os.path.dirname(jmd.__file__)
CONFIG_FILE = os.path.join(_DIR, 'config')

def writecsv(items):
    strlist = [str(items['source_id']), str(items['key2']), str(items['html']),
               str(items['request_info']), str(items['subject']), str(items['question_type'])]
    strs = ','.join(strlist)
    f.writelines(strs + '\n')

def remove_biaoqian(str_bioaqian):
    if isinstance(str_bioaqian, str):
        # str_bioaqian = str_bioaqian.replace('<\/v>','').replace('<label>','').replace('&nbsp;',' ')
        # str_bioaqian = str_bioaqian.replace('<\/tr>', '</tr>').replace('<\/td>', '</td>').replace('<\/pos>','</pos>')
        # str_bioaqian = str_bioaqian.replace('<\/label>','').replace('<\/div>','</div>').replace('<\/li>','')
        # str_bioaqian = str_bioaqian.replace('<\/ul>','/ul').replace('<v>','').replace('<\/span>','</span>')
        # str_bioaqian = str_bioaqian.replace('<p>', '').replace('<\\/p>', '').replace('; ; ; ;','')
        # str_bioaqian = str_bioaqian.replace('&nbsp', ' ').replace('<u>','').replace('; ; ;','')
        # str_bioaqian = str_bioaqian.replace('; ;', ' ').replace('\/data','/data').replace('<\\/u>','')
        # str_bioaqian = str_bioaqian.replace('<\/sub>','</sub>').replace('<\/sup>','</sup>')
        # str_bioaqian = str_bioaqian.replace('<pos>', '').replace('<\\/pos>', '').replace('<\/ b>','</ b>')
        # str_bioaqian = str_bioaqian.replace('<br \\/>','<br />').replace('\/','/').replace('<\/p>','')
        str_bioaqian = str_bioaqian.replace('&nbsp;',' ').replace('; ; ; ;','').replace("\\/",'/')
        str_bioaqian = str_bioaqian.replace('; ; ;','').replace('&nbsp', ' ')
        str_bioaqian = str_bioaqian.replace('; ;', ' ').replace('\/','/')
        return str_bioaqian
    else:
        print("插入的不是str格式！")

def replace_href(strings):
    if strings:
        strinfo = re.search('id="(.+?)"',strings)
        if strinfo is not None:
            strings = strings.replace(strinfo.group(),'')
        strings = strings.replace('src="/', 'src="http://www.yitiku.cn/').replace('src=""', '').replace('alt="菁优网"','alt="阿凡题"')
    return strings

def Data_to_MySQL(datas):
    #采用同步的机制写入mysql
    config = json.load(open(CONFIG_FILE))
    conn = pymysql.connect(host=config['host'], user=config['user'], passwd=config['password'], db='question_db_offline',
                           port=3306, charset= "utf8", use_unicode=True, cursorclass = pymysql.cursors.DictCursor)
    cursor = conn.cursor()

    record_dict = {
        'spider_source':59,
        'spider_url': datas['spider_url'],
        'knowledge_point': datas['knowledge_point'],
        'subject': datas['subject'],
        'difficulty': datas['difficulty'],
        'question_type_name': datas['question_type'],
        'question_html': datas["question_body"],
        'answer_all_html': datas["answer"],
        'fenxi': datas["analy"],
        'html_id': datas["question_id"],
        'question_type_name': datas['question_type_name'],
        'question_type': datas['question_type'],
        'paper_name_abbr': datas['paper_name'],
        'zhuanti': '',
        'exam_year': '',
        'exam_city': '',
        'question_quality': '',
        'option_html': '',
        'jieda': '',
        'dianping': ''
    }

    cols, values = zip(*record_dict.items())

    insert_sql = 'insert ignore into {table} ({cols}) values ({values})'.format(
        table='yitiku_doc_no_20170904',
        cols=', '.join(['`%s`' % col for col in cols]),
        values=', '.join(['%s' for col in cols])
    )

    if len(datas['question_body']) != 0:
        try:
            cursor.execute(insert_sql, values)
        except Exception as e:
            print(e)
    conn.commit()

def tableToJson(table):
    config = json.load(open(CONFIG_FILE))
    first_id = 0
    conn = pymysql.connect(host=config['host'], user=config['user'], passwd=config['password'], db='html_archive',
                           port=3306, charset= "utf8", use_unicode=True, cursorclass = pymysql.cursors.DictCursor)
    cur = conn.cursor()
    #sql = 'select * from {} where topic not like "%yitikuimage.oss-cn-qingdao.aliyuncs.com%" '.format(table)
    while True:
        logging.warn('parse the first_id is : {}'.format(first_id))
        sql = 'select * from {0} where html_id > {1} and topic not like "%yitikuimage.oss-cn-qingdao.aliyuncs.com%"  limit 100'.format(table, first_id)
        cur.execute(sql)
        data = cur.fetchall()
        # cur.close()

        if not data:
            break

        try:
            Parser(data)
        except Exception as e:
            print(e)

        first_id = int(data[-1]['html_id'])

def Parser(data):
    for row in data:
        result = parse_detail(row)
        try:
            Data_to_MySQL(result)
        except Exception as e:
            print(e)


def parse_detail(row):
    pattern_item = {
        '单选': '1',
        '填空': '2',
        '多选': '4'
    }
    spider_source = int(row['spider_source'])
    spider_url = row['spider_url']
    image_parse = HtmlMagic(spider_source=spider_source, download=True, archive_image=False)
    result1 = {}

    pattern = row['pattern']
    result1['question_type_name'] = pattern
    for key, value in pattern_item.items():
        if key in pattern:
            pattern = value
    if len(pattern) >= 2:
        pattern = '3'
    result1['question_type'] = pattern

    topic = row['topic']
    topic = replace_href(topic)
    topic = remove_tags(text=topic, which_ones=('h1', 'div'))
    topic = image_parse.bewitch(html_string=topic, spider_url=spider_url,
                                spider_source=spider_source)
    #result1['question_body'] = topic
    answer = row['answer']
    answer = replace_href(answer)
    answer = image_parse.bewitch(html_string=answer, spider_url=spider_url,
                                 spider_source=spider_source)
    #result1['answer'] = answer
    analy = row['analy']
    analy = replace_href(analy)
    analy = image_parse.bewitch(html_string=analy, spider_url=spider_url,
                                spider_source=spider_source)
    #result1['analy'] = analy
    _question = Question(question_body=topic,
                         answer=answer,
                         analy=analy, )
    standard_question = _question.normialize()
    result1['question_body'] = standard_question['question_body']
    result1['answer'] = standard_question['answer']
    result1['analy'] = standard_question['analy']

    source_shijuan = row['source_shijuan']
    source_shijuan = re.findall('<span class="colf43">来源：(.+?)</span>', source_shijuan)
    if len(source_shijuan) != 0:
        result1['paper_name'] = source_shijuan[0]
    else:
        result1['paper_name'] = ''

    mapping_dict = {
        'question_id': 'source_id',
        'subject': 'subject',
        'spider_url': 'spider_url',
        'knowledge_point': 'kaodian',
        'difficulty': 'difficulty',
        'source': 'spider_source',
        'spider_source': 'spdier_source'
    }
    result2 = {
        key: row.get(value, '')
        for key, value in mapping_dict.items()
    }

    result = dict(result1, **result2)

    return result

if __name__ == '__main__':
    jsonData = tableToJson('yitiku_shiti_no_0901')

