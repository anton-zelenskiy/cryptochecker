class Config:
    JOBS = [
        {
            'id': 'sent_currencies_price',
            'func': 'project.scheduler.tasks:send_currency_prices',
            'args': (),
            'trigger': 'cron',
            'hour': '*/1'
        },
        {
            'id': 'check_volatility',
            'func': 'project.scheduler.tasks:check_volatility',
            'args': (),
            'trigger': 'cron',
            'minute': '*/5',
        },
    ]
    SCHEDULER_API_ENABLED = True
