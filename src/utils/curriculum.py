from datetime import datetime, date, time, timedelta

from dateutil import tz


# 某一门课程
class Curriculum:
    def __init__(self, is_single, weekday, start, end, place, name, teacher, students):
        self.is_single = is_single
        self.weekday = weekday
        self.start = start
        self.end = end
        self.place = place
        self.name = name
        self.teacher = teacher
        self.students = students

    def get_class(self, cur_date):
        return Class(cur_date, self.is_single, self.weekday, self.start, self.end, self.place, self.name, self.teacher,
                     self.students)


# 具体某一天的某一节课
class Class(Curriculum):
    def __init__(self, cur_date, is_single, weekday, start, end, place, name, teacher, students):
        super().__init__(is_single, weekday, start, end, place, name, teacher, students)
        self.date = cur_date
        self.shifted = False

    def __lt__(self, other):
        return self.date < other.date or (self.date == other.date and self.start < other.start)

    def __eq__(self, other):
        return self.date == other.date and self.start == other.start and self.end == other.end and self.place == other.place

    def __hash__(self):
        return (self.date.strftime('%Y-%m-%d') + self.start.strftime('%H:%M') + self.place + str(
            self.is_single)).__hash__()


class ShiftInfo:
    def __init__(self, course, date_info, start, end, place):

        self.course = course
        self.date = datetime.strptime(date_info, "%Y-%m-%d").replace(
            tzinfo=tz.gettz('Asia/Shanghai')).date()
        self.start = datetime.strptime(start, "%H:%M").replace(
            tzinfo=tz.gettz('Asia/Shanghai')).time()
        self.end = datetime.strptime(end, "%H:%M").replace(
            tzinfo=tz.gettz('Asia/Shanghai')).time()
        self.place = place


class Shift:
    def __init__(self, source, target):
        self.source = source
        self.target = target


def cal_single(ref_date, cur_single, target_date):
    days = (target_date - ref_date).days
    days = days % 14
    return cur_single if ref_date.weekday() + days < 7 else not cur_single
