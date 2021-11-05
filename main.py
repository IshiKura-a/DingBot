import json
from datetime import datetime
from bs4 import BeautifulSoup
from dateutil import tz
import urllib3
from tqdm.contrib.concurrent import process_map
from apscheduler.schedulers.blocking import BlockingScheduler
import requests

config = {}
try:
    config = json.load(open('config.json', 'r'))
except FileNotFoundError:
    print('config.json not found!')
    exit(1)

assert config['ding_bot_url'] is not None
assert config['questionary_url'] is not None


def parse_time(time_str):
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=tz.gettz('Asia/Shanghai'))


def read_log():
    try:
        with open('record.log') as f:
            line = f.readline()
            return parse_time(line)
    except FileNotFoundError:
        return None


def send_msg(content, href, time):
    http = urllib3.PoolManager()
    url = config['ding_bot_url']
    r = http.request('POST', url, headers={
        "Content-Type": "application/json"
    }, body=json.dumps({
        "msgtype": "markdown",
        "markdown": {
            "title": f'[朋辈辅学] {time.strftime("%Y-%m-%d %H:%M:%S")}',
            "text": content + f'\n\n原文链接：[链接]({href})'
        }, "at": {
            "isAtAll": False
        }
    }))
    result = json.loads(r.data)
    if str(result['errcode']) == '0':
        print(f'Snapshot:\n{str(content)[0:10]}...\n推送成功!')
    else:
        print(f'Snapshot:\n{str(content)[0:10]}...\n推送失败!')
        print(result)


def download(item):
    http = urllib3.PoolManager()
    r = http.request('GET', item['href'], preload_content=False)
    data = r.data.decode(encoding='utf-8')
    r.release_conn()
    return data


def main():
    current_time = datetime.now(tz.gettz('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S")
    last_time = read_log()

    data_url = config['questionary_url']
    page = requests.get(data_url).content.decode(encoding='UTF-8')
    soup = BeautifulSoup(page, features="html.parser")
    table = soup.find(attrs={'class': 'table-content'}).find_all('tr')[1:]

    data = []
    for row in table:
        href = ''
        time = None
        for column in row.find_all('td'):
            result = column.find('a')
            if result is not None:
                href = result.attrs['href']
            else:
                result = column.find('div')
                time = parse_time(result.attrs['title'])
        if last_time is None or last_time < time:
            data.append({
                'href': href,
                'time': time
            })

    print(f'Got {len(data)} new questions')
    questions = process_map(download, data)

    for i in range(len(questions)):
        send_msg(questions[i].replace('\r\n', '\n'), data[i]['href'], data[i]['time'])

    with open('record.log', 'w') as f:
        f.write(current_time)
    return


if __name__ == '__main__':
    schedule = BlockingScheduler()
    schedule.add_job(main, 'interval', minutes=10, next_run_time=datetime.now())
    schedule.print_jobs()
    schedule.start()
