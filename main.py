import json
import os
import random
from urllib.parse import quote
import re
import sys
from datetime import datetime, timedelta, time

from apscheduler.events import EVENT_JOB_ERROR
from bs4 import BeautifulSoup
from dateutil import tz
import urllib3
from tqdm.contrib.concurrent import process_map
from apscheduler.schedulers.blocking import BlockingScheduler
import argparse
import requests
import logging

import util
from Curriculum import Curriculum, Shift, cal_single

parser = argparse.ArgumentParser()
parser.add_argument("--test", action='store_true')

args = parser.parse_args()
start_time = datetime.now(tz.gettz('Asia/Shanghai'))
schedule = BlockingScheduler(timezone='Asia/Shanghai')
config = {}
class_list = []
try:
    config = json.load(open('config.json', 'r'))
except FileNotFoundError:
    logging.critical('config.json not found!')
    exit(1)

assert (config['access_token'] is not None) if not args.test else (config['test_access_token'] is not None)
assert (config['secret'] is not None) if not args.test else (config['test_secret'] is not None)
assert config['questionnaire_url'] is not None
assert config['is_single_now'] is not None

if not os.path.exists('input/timetable.csv'):
    logging.critical('timetable.csv not found!')
    exit(1)

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
if args.test:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=LOG_FORMAT)
else:
    logging.basicConfig(filename='record.log', level=logging.INFO, format=LOG_FORMAT, filemode='a')


def schedule_listener(event):
    if event.exception:
        logging.error(event.traceback)


def read_log():
    return None if config.get('question_timestamp') is None else util.parse_time(config['question_timestamp'])


def send_msg(msg_type, content, at=None):
    if at is None:
        at = {}
    http = urllib3.PoolManager()

    access_token = config['test_access_token'] if args.test else config['access_token']
    timestamp = str(round(datetime.now(tz.gettz('Asia/Shanghai')).timestamp() * 1000))
    sign = util.get_sign(config['test_secret'] if args.test else config['secret'], timestamp)

    r = http.request('POST',
                     f"https://oapi.dingtalk.com/robot/send?access_token={access_token}&timestamp={timestamp}&sign={sign}",
                     headers={
                         "Content-Type": "application/json",
                     },
                     body=json.dumps({
                         "msgtype": msg_type,
                         msg_type: content,
                         "at": at
                     }))
    result = json.loads(r.data)
    if str(result['errcode']) == '0':
        logging.info(f'Snapshot:\n{str(content)[0:50]}...\n推送成功!')
    else:
        logging.error(f'Snapshot:\n{str(content)[0:50]}...\n推送失败!')
        logging.error(result)


def raise_question():
    last_time = read_log()
    current_time = datetime.now(tz.gettz('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")
    data_url = config['questionnaire_url']
    page = requests.get(data_url).content.decode(encoding='UTF-8')
    soup = BeautifulSoup(page, features="html.parser")
    table = soup.find(attrs={'class': 'table-content'}).find_all('tr')[1:]

    data = []
    for row in table:
        href = ''
        upload_time = None
        for column in row.find_all('td'):
            result = column.find('a')
            if result is not None:
                href = result.attrs['href']
            else:
                result = column.find('div')
                upload_time = util.parse_time(result.attrs['title'])
        if last_time is None or last_time < upload_time:
            data.append({
                'href': href,
                'time': upload_time
            })

    logging.info(f'Got {len(data)} new questions')
    questions = process_map(util.download, data)

    for i in range(len(questions)):
        send_msg('markdown', {
            "title": f'[朋辈辅学] {data[i]["time"].strftime("%Y-%m-%d %H:%M:%S")}',
            "text": questions[i].replace('\r\n', '\n')
        })

    config['question_timestamp'] = current_time
    json.dump(config, open('config.json', 'w'))
    return


def get_curricula():
    curricula = []
    weekdays = ['周' + i for i in ['一', '二', '三', '四', '五', '六', '日']]

    with open('input/timetable.csv', 'r', encoding='UTF-8') as f:
        for line in f.readlines():
            line = line.strip().split(',')
            is_single = line[0] == '单'
            weekday = weekdays.index(line[1])
            start_h, start_m, end_h, end_m = [int(i) for i in re.compile(r'(\d{1,2})').findall(line[2])]
            if re.search(r'上午', line[2]) is None:
                start_h += 12
                end_h += 12
            place = line[3]
            students = line[5].split('、')
            start = time(start_h, start_m, 0, 0)
            end = time(end_h, end_m, 0, 0)
            curricula.append(Curriculum(is_single, weekday, start, end, place, course, teacher, students))
    return curricula


def get_corpus():
    with open('./input/corpus.csv', 'r', encoding='UTF-8') as f:
        return list(filter(lambda x: x != '', [line.strip() for line in f.readlines()]))


def inform():
    curricula = get_curricula()
    shifts = Shift.get_shift()
    corpus = get_corpus()
    current_time = datetime.now(tz.gettz('Asia/Shanghai'))
    weekday = current_time.date().weekday()

    if start_time.date() != current_time.date() and weekday == 0:
        config['is_single_now'] = not config['is_single_now']

    global class_list
    class_list = sorted(list(filter(lambda x: x.date >= current_time.date(), class_list)))

    for curriculum in curricula:
        if curriculum.is_single == config['is_single_now'] and curriculum.weekday == weekday:
            class_list.append(curriculum.get_class(current_time.date()))

    for shift in shifts:
        source = shift.source
        target = shift.target
        for i in class_list:
            if source.date == i.date and source.start == i.start and source.place == i.place:
                logging.info(
                    f'{i.name} shifted from {i.date.strftime("%Y-%m-%d")} {i.start.strftime("%H:%M")} to {target.date.strftime("%Y-%m-%d")} {target.start.strftime("%H:%M")}')
                i.date = target.date
                i.start = target.start
                i.end = target.end
                i.place = target.place
                i.shifted = True

        if target.date == current_time.date():
            for i in curricula:
                if i.weekday == source.date.weekday() and i.start == source.start and i.place == source.place and i.is_single == cal_single(
                        current_time.date(), config['is_single_now'], source.date):
                    logging.info(
                        f'{i.name}（{i.place}） shifted from {source.date.strftime("%Y-%m-%d")} {i.start.strftime("%H:%M")} to {target.date.strftime("%Y-%m-%d")} {target.start.strftime("%H:%M")}')
                    new_class = i.get_class(current_time.date())
                    new_class.start = shift.target.start
                    new_class.end = shift.target.end
                    new_class.place = shift.target.place
                    new_class.shifted = True
                    class_list.append(new_class)

    class_list = list(set(class_list))
    today_class = sorted(list(filter(lambda x: x.date == current_time.date(), class_list)))
    if len(today_class) > 0:
        send_msg('text', {
            'content': f'早安[比心], 今天一共有{len(today_class)}门课:\n\n' + '\n'.join([
                f'{i + 1}. {cur.name + ("（调课）" if cur.shifted else "")}[{cur.teacher}][{cur.place}, {cur.start.strftime("%H:%M")}:{cur.end.strftime("%H:%M")}]\n学生: {"、".join(cur.students)}\n'
                for i, cur in enumerate(today_class)
            ]) + '\n大家要准时上课哦[天使]'
        }, at={'isAtAll': True})
    else:
        send_msg('text', {
            'content': random.choice(corpus)
        })

    for i in today_class:
        schedule.add_job(send_msg, 'date',
                         next_run_time=datetime.combine(i.date, i.start, tzinfo=tz.gettz('Asia/Shanghai')) - timedelta(
                             minutes=15),
                         args=['text', {
                             'content': f'课程: {i.name}[{i.teacher}][{i.place}, {i.start.strftime("%H:%M")}-{i.end.strftime("%H:%M")}]即将开始，老师同学们不要忘啦[微笑]'
                         }])

    schedule.print_jobs()
    schedule.start()
    return


def information_remind():
    last_time = read_log()
    current_time = datetime.now(tz.gettz('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")
    data_url = config['questionnaire_url']
    page = requests.get(data_url).content.decode(encoding='UTF-8')
    soup = BeautifulSoup(page, features="html.parser")
    table = soup.find(attrs={'class': 'table-content'}).find_all('tr')[1:]
    data = []
    for row in table:
        tb = []
        for column in row.find_all('td'):
            result = column.find('div')
            tb.append(result.attrs['title'])
        upload_time = util.parse_time(tb[3])
        if last_time is None or last_time < upload_time:
            data.append({
                'time': upload_time,
                'start_time': datetime.strptime(tb[0], "%Y-%m-%d %H:%M") - timedelta(minutes=5),
                'end_time': datetime.strptime(tb[1], "%Y-%m-%d %H:%M"),
                "course_name": tb[2]
            })

    logging.info(f'Got {len(data)} new courses')
    logging.info(data)

    for task in data:
        schedule.add_job(send_msg, trigger=None, next_run_time=task['start_time'], args=('markdown', {
            "title": f'[朋辈辅学] {task["time"].strftime("%Y-%m-%d %H:%M:%S")}',
            "text": str(task['course_name']) + " 课程将在五分钟后开始哟~"
        }))
        schedule.add_job(send_msg, trigger=None, next_run_time=task['end_time'], args=('text', {
            "title": f'[朋辈辅学] {task["time"].strftime("%Y-%m-%d %H:%M:%S")}',
            "content": '欢迎大家填写问卷反馈[送花花]\nhttps://jinshuju.net/f/VoPZf4'
        }))
    schedule.print_jobs()
    config['question_timestamp'] = current_time
    json.dump(config, open('config.json', 'w'))
    return


if __name__ == '__main__':
    logging.info(args)

    if args.test:
        schedule.add_job(information_remind, 'interval', minutes=5, next_run_time=datetime.now())
        schedule.print_jobs()
        schedule.start()
    else:
        if start_time.time() > time(8, 0, 0, 0):
            run_time = datetime.combine(start_time.date() + timedelta(days=1), time(8, 0, 0, 0))
        else:
            run_time = datetime.combine(start_time.date(), time(8, 0, 0, 0))

        #schedule.add_listener(schedule_listener, EVENT_JOB_ERROR)
        #schedule.add_job(raise_question, 'interval', minutes=10, next_run_time=datetime.now())
        # schedule.add_job(inform, 'interval', days=1, next_run_time=run_time)
        schedule.add_job(information_remind, 'interval', minutes=5, next_run_time=datetime.now())
        schedule.print_jobs()
        schedule.start()
