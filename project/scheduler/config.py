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
            'id': 'check_volatility_15',
            'func': 'project.scheduler.tasks:check_volatility',
            'args': (15,),
            'trigger': 'cron',
            'minute': '*/15',
        },
        {
            'id': 'check_volatility_30',
            'func': 'project.scheduler.tasks:check_volatility',
            'args': (30,),
            'trigger': 'cron',
            'minute': '*/30',
        },
        {
            'id': 'check_volatility_60',
            'func': 'project.scheduler.tasks:check_volatility',
            'args': (60,),
            'trigger': 'cron',
            'hour': '*/1',
        },
    ]
    SCHEDULER_API_ENABLED = True
