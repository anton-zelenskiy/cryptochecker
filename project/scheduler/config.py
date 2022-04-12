class Config:
    JOBS = [
        {
            'id': 'send_currency_prices',
            'func': 'project.scheduler.tasks:send_currency_prices',
            'args': (),
            'trigger': 'cron',
            'hour': '*/1'
        },
        {
            'id': 'check_volatility_5',
            'func': 'project.scheduler.tasks:check_volatility',
            'args': (5,),
            'trigger': 'cron',
            'minute': '*/5',
        },
        {
            'id': 'check_volatility_10',
            'func': 'project.scheduler.tasks:check_volatility',
            'args': (10,),
            'trigger': 'cron',
            'minute': '*/10',
        },
    ]
    SCHEDULER_API_ENABLED = True
