from datetime import datetime, date, time, timedelta

from dateutil import tz


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
    def __init__(self, date_info, start, end, place):
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

    @staticmethod
    def get_shift():
        shifts = []
        try:
            with open('./input/shift.csv', 'r', encoding='UTF-8') as f:
                for line in f.readlines():
                    line = line.strip().split(',')
                    source, target = ShiftInfo(*line[0:4]), ShiftInfo(*line[4:8])
                    shifts.append(Shift(source, target))
        except FileNotFoundError:
            pass
        finally:
            return shifts


def cal_single(ref_date, cur_single, target_date):
    days = (target_date - ref_date).days
    days = days % 14
    return cur_single if ref_date.weekday() + days < 7 else not cur_single
