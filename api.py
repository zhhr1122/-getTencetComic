#!/usr/bin/env python
# -*- coding: utf-8 -*- 
from flask import Flask, jsonify
import argparse
import json
import os
import re
import threading
from time import sleep

import requests
from lxml import html

requestSession = requests.session()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
      AppleWebKit/537.36 (KHTML, like Gecko) \
      Chrome/52.0.2743.82 Safari/537.36'  # Chrome on win10
requestSession.headers.update({'User-Agent': UA})


app = Flask(__name__)

tasks = [
    {
        'id': 1,
        'title': u'Buy groceries',
        'description': u'Milk, Cheese, Pizza, Fruit, Tylenol',
        'done': False
    },
    {
        'id': 2,
        'title': u'Learn Python',
        'description': u'Need to find a good Python tutorial on the web',
        'done': False
    }
]

@app.route('/todo/api/v1.0/tasks', methods=['GET'])
def get_tasks():
    return jsonify({'tasks': tasks})
    
from flask import abort

@app.route('/getChapterList/<int:task_id>/<int:list>', methods=['GET'])
def get_task(task_id,list):
    comiclist = getChapterList(task_id,list)
    return jsonify({'comiclist': comiclist})

@app.route('/getPreNowChapterList/<int:task_id>/<int:list>', methods=['GET'])
def get_task1(task_id,list):
    prelist = getChapterList(task_id,(list-1))
    nowlist = getChapterList(task_id,list)
    nextlist = getChapterList(task_id,(list+1))
    return jsonify(
                    {'prelist': prelist,
                     'nowlist': nowlist,
                     'nextlist': nextlist}
                   )
                   
@app.route('/getIndex/<int:task_id>', methods=['GET'])
def get_task2(task_id):
    comicName, comicIntrd, count, contentList = getContent(task_id)
    return jsonify(
                    {'name': comicName,
                     'introduce': comicIntrd,
                     'count': count,
                     'contentList': contentList
                     }
                   )

from flask import make_response

@app.errorhandler(404)
def not_found(error):
    comiclist = []
    return jsonify({'comiclist': comiclist})
    
class ErrorCode(Exception):
    '''自定义错误码:
        1: URL不正确
        2: URL无法跳转为移动端URL
        3: 中断下载'''

    def __init__(self, code):
        self.code = code

    def __str__(self):
        return repr(self.code)


def isLegelUrl(url):
    legal_url_list = [
        re.compile(r'^http://ac.qq.com/Comic/[Cc]omicInfo/id/\d+?'),
        re.compile(r'^http://m.ac.qq.com/Comic/[Cc]omicInfo/id/\d+?'),
        re.compile(r'^http://m.ac.qq.com/comic/index/id/\d+?'),
        re.compile(r'^http://ac.qq.com/\w+/?$'),
    ]

    for legal_url in legal_url_list:
        if legal_url.match(url):
            return True
    return False


def getId(url):
    if not isLegelUrl(url):
        print('请输入正确的url！具体支持的url请在命令行输入-h|--help参数查看帮助文档。')
        raise ErrorCode(1)

    numRE = re.compile(r'\d+$')

    id = numRE.findall(url)
    if not id:
        get_id_request = requestSession.get(url)
        url = get_id_request.url
        id = numRE.findall(url)
        if not isLegelUrl(url) or not id:
            print('无法自动跳转移动端URL，请进入http://m.ac.qq.com，找到'
                  '该漫画地址。\n'
                  '地址应该像这样: '
                  'http://m.ac.qq.com/Comic/comicInfo/id/xxxxx (xxxxx为整数)')
            raise ErrorCode(2)

    return id[0]


def getContent(id):
    comic_info_page = 'https://m.ac.qq.com/comic/index/id/{}'.format(id)
    page = requestSession.get(comic_info_page).text
    tree = html.fromstring(page)
    comic_name_xpath = '/html/body/article/div[1]/section[1]/div[2]/div[2]/ul/li[1]/h1/text()'
    comicName = tree.xpath(comic_name_xpath)[0].strip()
    comic_intro_xpath = '/html/body/article/div[2]/section[1]/div/p/text()'
    comicIntrd = tree.xpath(comic_intro_xpath)[0].strip()

    chapter_list_page = 'https://m.ac.qq.com/comic/chapterList/id/{}'.format(id)
    page = requestSession.get(chapter_list_page).text
    tree = html.fromstring(page)
    chapter_list_xpath = '/html/body/section[2]/ul[2]/li/a'
    chapter_list = tree.xpath(chapter_list_xpath)
    count = len(chapter_list)
    sortedContentList = []

    for chapter_element in chapter_list:
        sortedContentList.append(
            {'name': chapter_element.text, 'url': 'https://m.ac.qq.com' + chapter_element.get('href')})

    print(sortedContentList)

    return (comicName, comicIntrd, count, sortedContentList)


def getImgList(chapter_url):
    retry_num = 0
    retry_max = 5
    while True:
        try:
            chapter_page = requestSession.get(chapter_url, timeout=5).text
            base64data = re.findall(r"data:\s*'(.+?)'", chapter_page)[0][1:]
            img_detail_json = json.loads(__decode_base64_data(base64data))
            imgList = []
            for img_url in img_detail_json.get('picture'):
                imgList.append(img_url['url'])
            return imgList
            break
        except (KeyboardInterrupt, SystemExit):
            print('\n\n中断下载！')
            raise ErrorCode(3)
        except:
            retry_num += 1
            if retry_num >= retry_max:
                raise
            print('下载失败，重试' + str(retry_num) + '次')
            sleep(2)

    return []


def __decode_base64_data(base64data):
    base64DecodeChars = [- 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
                         -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1,
                         63, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1, -1, 0, 1, 2, 3, 4, 5, 6, 7,
                         8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1, -1,
                         26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49,
                         50, 51, -1, -1, -1, -1, -1]
    data_length = len(base64data)
    i = 0
    out = ""
    c1 = c2 = c3 = c4 = 0
    while i < data_length:
        while True:
            c1 = base64DecodeChars[ord(base64data[i]) & 255]
            i += 1
            if not (i < data_length and c1 == -1):
                break
        if c1 == -1:
            break
        while True:
            c2 = base64DecodeChars[ord(base64data[i]) & 255]
            i += 1
            if not (i < data_length and c2 == -1):
                break
        if c2 == -1:
            break
        out += chr(c1 << 2 | (c2 & 48) >> 4)
        while True:
            c3 = ord(base64data[i]) & 255
            i += 1
            if c3 == 61:
                return out
            c3 = base64DecodeChars[c3]
            if not (i < data_length and c3 == - 1):
                break
        if c3 == -1:
            break
        out += chr((c2 & 15) << 4 | (c3 & 60) >> 2)
        while True:
            c4 = ord(base64data[i]) & 255
            i += 1
            if c4 == 61:
                return out
            c4 = base64DecodeChars[c4]
            if not (i < data_length and c4 == - 1):
                break
        out += chr((c3 & 3) << 6 | c4)
    return out




def parseLIST(lst):
    '''解析命令行中的-l|--list参数，返回解析后的章节列表'''
    legalListRE = re.compile(r'^\d+([,-]\d+)*$')
    if not legalListRE.match(lst):
        raise AttributeError(lst + ' 不匹配正则: ' + r'^\d+([,-]\d+)*$')

    # 先逗号分割字符串，分割后的字符串再用短横杠分割
    parsedLIST = []
    sublist = lst.split(',')
    numRE = re.compile(r'^\d+$')

    for sub in sublist:
        if numRE.match(sub):
            if int(sub) > 0:  # 自动忽略掉数字0
                parsedLIST.append(int(sub))
            else:
                print('警告: 参数中包括不存在的章节0，自动忽略')
        else:
            splitnum = list(map(int, sub.split('-')))
            maxnum = max(splitnum)
            minnum = min(splitnum)  # min-max或max-min都支持
            if minnum == 0:
                minnum = 1  # 忽略数字0
                print('警告: 参数中包括不存在的章节0，自动忽略')
            parsedLIST.extend(range(minnum, maxnum + 1))

    parsedLIST = sorted(set(parsedLIST))  # 按照从小到大的顺序排序并去重
    return parsedLIST



def getChapterList(id,lst):
    '''url: 要爬取的漫画首页。 path: 漫画下载路径。 lst: 要下载的章节列表(-l|--list后面的参数)'''
    try:
        comicName, comicIntrd, count, contentList = getContent(id)
        imgList = []
        imgList = getImgList(contentList[lst]['url'])
        return imgList
    except ErrorCode as e:
        return "error"
        exit(e.code)

        
   

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5001,debug=True)
