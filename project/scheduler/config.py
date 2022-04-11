from apscheduler.triggers.cron import CronTrigger


class Config:
    # JOBS = [
    #     {
    #         'id': 'sent_currencies_price',
    #         'func': 'project.scheduler.tasks:send_currency_prices',
    #         'args': (),
    #         'trigger': 'interval',
    #         'minutes': 60
    #     },
    #     {
    #         'id': 'check_volatility',
    #         'func': 'project.scheduler.tasks:check_volatility',
    #         'args': (),
    #         'trigger': 'interval',
    #         'minutes': 5,
    #     },
    # ]
    SCHEDULER_API_ENABLED = True


cron_send_currencies_price = CronTrigger(hour='*/1', timezone='Asia/Tbilisi')
cron_check_volatility = CronTrigger(minute='*/5', timezone='Asia/Tbilisi')
