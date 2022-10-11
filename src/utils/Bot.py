import json
import logging
import random
import requests
import re
import sys
import urllib3

from apscheduler.schedulers.blocking import BlockingScheduler
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, time
from dateutil import tz
from tqdm.contrib.concurrent import process_map

from src.utils import util
from src.utils.Curriculum import Curriculum, Shift, ShiftInfo, cal_single


class Bot:
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

    def __init__(self, config_path: str, test_flag: bool):
        self.scheduler = BlockingScheduler(timezone='Asia/Shanghai')
        self.test = test_flag

        try:
            self.config = json.load(open(config_path, 'r'))
            assert self.config['log_path'] is not None
            if test_flag:
                assert self.config['test_access_token'] is not None
                assert self.config['test_secret'] is not None
            else:
                assert self.config['access_token'] is not None
                assert self.config['secret'] is not None
        except FileNotFoundError:
            logging.critical('config.json not found!')
            exit(1)
        except AssertionError:
            logging.critical('invalid config file: ' + config_path)
            exit(1)

        if test_flag:
            logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=Bot.LOG_FORMAT)
        else:
            logging.basicConfig(filename=self.config['log_path'], level=logging.INFO, format=Bot.LOG_FORMAT, filemode='a')

    # 向钉钉群推送消息
    def send_msg(self, msg_type, content, at=None):
        if at is None:
            at = {}
        http = urllib3.PoolManager()

        access_token = self.config['test_access_token'] if self.test else self.config['access_token']
        timestamp = str(round(datetime.now(tz.gettz('Asia/Shanghai')).timestamp() * 1000))
        sign = util.get_sign(self.config['test_secret'] if self.test else self.config['secret'], timestamp)

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


class QuestionBot(Bot):

    def __init__(self, config_path: str, test_flag: bool):
        super(QuestionBot, self).__init__(config_path, test_flag)

        try:
            assert self.config['questionnaire_url'] is not None
        except AssertionError:
            logging.critical('invalid config file: ' + config_path)
            exit(1)

    def get_last_question_time(self):
        if self.config.get('last_question_timestamp') is None:
            return None
        else:
            return util.parse_time(self.config['last_question_timestamp'])

    def raise_question(self):
        last_time = self.get_last_question_time()
        current_time = datetime.now(tz.gettz('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")
        data_url = self.config['questionnaire_url']
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
            self.send_msg('markdown', {
                "title": f'[朋辈辅学] {data[i]["time"].strftime("%Y-%m-%d %H:%M:%S")}',
                "text": questions[i].replace('\r\n', '\n') + f'\n'
            })

        self.config['last_question_timestamp'] = current_time
        json.dump(self.config, open('config.json', 'w'))

    def schedule(self):
        self.scheduler.add_job(self.raise_question, 'interval', minutes=10, next_run_time=datetime.now())
        self.scheduler.start()


class CourseReMinderBot(Bot):

    def __init__(self, config_path: str, test_flag: bool):
        super(CourseReMinderBot, self).__init__(config_path, test_flag)
        self.start_time = datetime.now(tz.gettz('Asia/Shanghai'))  # used for check 单双周
        self.config_path = config_path
        self.class_list = []

        try:
            assert self.config['is_single_now'] is not None
            assert self.config['corpus_path'] is not None
            assert self.config['curricula_path'] is not None
            assert self.config['shifts_path'] is not None
        except AssertionError:
            logging.critical('invalid config file: ' + config_path)
            exit(1)

    def get_corpus(self):
        try:
            with open(self.config['corpus_path'], 'r', encoding='UTF-8') as f:
                return list(filter(lambda x: x != '', [line.strip() for line in f.readlines()]))
        except FileNotFoundError:
            logging.critical('file not found: ' + self.config['corpus_path'])
            exit(1)

    def get_curricula(self):
        curricula = []
        weekdays = ['周' + i for i in ['一', '二', '三', '四', '五', '六', '日']]
        try:
            with open(self.config['curricula_path'], 'r', encoding='UTF-8') as f:
                for line in f.readlines():
                    line = line.strip().split(',')
                    is_single = line[0] == '单'
                    weekday = weekdays.index(line[1])
                    start_h, start_m, end_h, end_m = [int(i) for i in re.compile(r'(\d{1,2})').findall(line[2])]
                    if re.search(r'上午', line[2]) is None:
                        start_h += 12
                        end_h += 12
                    place = line[3]
                    course = re.compile(r'(.+)（.{2,4}）').findall(line[4])[0]
                    teacher = re.compile(r'（(.{2,4})）').findall(line[4])[0]
                    students = line[5].split('、')
                    start = time(start_h, start_m, 0, 0)
                    end = time(end_h, end_m, 0, 0)
                    curricula.append(Curriculum(is_single, weekday, start, end, place, course, teacher, students))
        except FileNotFoundError:
            pass
        return curricula

    def get_shifts(self):
        shifts = []
        try:
            with open(self.config['shifts_path'], 'r', encoding='UTF-8') as f:
                for line in f.readlines():
                    line = line.strip().split(',')
                    source, target = ShiftInfo(*line[0:4]), ShiftInfo(*line[4:8])
                    shifts.append(Shift(source, target))
        except FileNotFoundError:
            pass
        return shifts

    def inform(self):
        curricula = self.get_curricula()
        shifts = self.get_shifts()
        corpus = self.get_corpus()
        current_time = datetime.now(tz.gettz('Asia/Shanghai'))
        weekday = current_time.date().weekday()

        if self.start_time.date() != current_time.date() and weekday == 0:
            self.config['is_single_now'] = not self.config['is_single_now']
            json.dump(self.config, open(self.config_path, 'w'))

        self.class_list = sorted(list(filter(lambda x: x.date >= current_time.date(), self.class_list)))

        for curriculum in curricula:
            if curriculum.is_single == self.config['is_single_now'] and curriculum.weekday == weekday:
                self.class_list.append(curriculum.get_class(current_time.date()))

        for shift in shifts:
            source = shift.source
            target = shift.target
            # 当日课程调换到后面
            for i in self.class_list:
                if source.date == i.date and source.start == i.start and source.place == i.place:
                    logging.info(
                        f'{i.name} shifted from {i.date.strftime("%Y-%m-%d")} {i.start.strftime("%H:%M")} to {target.date.strftime("%Y-%m-%d")} {target.start.strftime("%H:%M")}')
                    i.date = target.date
                    i.start = target.start
                    i.end = target.end
                    i.place = target.place
                    i.shifted = True

            # 后面的课程调换到今天
            if target.date == current_time.date():
                for i in curricula:
                    if i.weekday == source.date.weekday() and i.start == source.start and i.place == source.place \
                            and i.is_single == cal_single(current_time.date(), self.config['is_single_now'],
                                                          source.date):
                        logging.info(
                            f'{i.name}（{i.place}） shifted from {source.date.strftime("%Y-%m-%d")} {i.start.strftime("%H:%M")} to {target.date.strftime("%Y-%m-%d")} {target.start.strftime("%H:%M")}')
                        new_class = i.get_class(current_time.date())
                        new_class.start = shift.target.start
                        new_class.end = shift.target.end
                        new_class.place = shift.target.place
                        new_class.shifted = True
                        self.class_list.append(new_class)

        class_list = list(set(self.class_list))
        today_class = sorted(list(filter(lambda x: x.date == current_time.date(), class_list)))
        if len(today_class) > 0:
            self.send_msg('text', {
                'content': f'早安[比心], 今天一共有{len(today_class)}门课:\n\n' + '\n'.join([
                    f'{i + 1}. {cur.name + ("（调课）" if cur.shifted else "")}[{cur.teacher}][{cur.place}, {cur.start.strftime("%H:%M")}:{cur.end.strftime("%H:%M")}]\n学生: {"、".join(cur.students)}\n'
                    for i, cur in enumerate(today_class)
                ]) + '\n大家要准时上课哦[天使]'
            }, at={'isAtAll': True})
        else:
            self.send_msg('text', {
                'content': random.choice(corpus)
            })

        for i in today_class:
            self.scheduler.add_job(
                self.send_msg, 'date',
                next_run_time=datetime.combine(i.date, i.start,
                                               tzinfo=tz.gettz('Asia/Shanghai')) - timedelta(
                    minutes=15),
                args=['text', {
                    'content': f'课程: {i.name}[{i.teacher}][{i.place}, {i.start.strftime("%H:%M")}-{i.end.strftime("%H:%M")}]即将开始，老师同学们不要忘啦[微笑]'
                }])

    def schedule(self):
        self.scheduler.add_job(self.inform, 'interval', minutes=10, next_run_time=datetime.now())
        self.scheduler.start()
