import argparse

from src.utils.bot import *


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action='store_true')
    args = parser.parse_args()

    course_reminder_bot = CourseReMinderBot("config/course_reminder_bot_config.json", args.test)
    course_reminder_bot.schedule()
    question_bot = QuestionBot("config/question_bot_config.json", args.test)
    question_bot.schedule()
    start()
