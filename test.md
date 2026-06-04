def _get_holiday_lookup() -> dict[str, str]:
    now = get_current_time()
    current_year = now.year
    lookup = {}
    db_holidays = Holiday.query.filter(
        db.or_(
            Holiday.is_recurring.is_(True),
            db.extract('year', Holiday.date) == current_year
        )
    ).all()
    for holiday in db_holidays:
        key = holiday.date.strftime("%m-%d")
        lookup[key] = holiday.name
    for holiday_key, holiday_name in VN_FIXED_PUBLIC_HOLIDAYS.items():
        lookup.setdefault(holiday_key, holiday_name)
    lunar_holidays = OvertimeConfig.get_lunar_holidays(current_year)
    for holiday_key, holiday_name in lunar_holidays.items():
        lookup.setdefault(holiday_key, holiday_name)
    return lookup