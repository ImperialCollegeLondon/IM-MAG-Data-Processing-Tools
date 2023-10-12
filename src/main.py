"""Main module."""

import datetime

import typer

import check_gaps

app = typer.Typer()

app.add_typer(check_gaps.app, name="check-gap")


@app.command()
def countdown():
    print(f"IMAP launch is {get_relative_time(datetime.datetime(2025, 2, 25))}")


SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
MONTH = 30 * DAY


def get_relative_time(dt):
    now = datetime.datetime.now()
    delta_time = dt - now

    delta = delta_time.days * DAY + delta_time.seconds
    minutes = delta / MINUTE
    hours = delta / HOUR
    days = delta / DAY

    if delta < 0:
        return "already happened"

    if delta < 1 * MINUTE:
        if delta == 1:
            return "one second to go"
        else:
            return str(delta) + " seconds to go"

    if delta < 2 * MINUTE:
        return "a minute ago"

    if delta < 45 * MINUTE:
        return str(minutes) + " minutes to go"

    if delta < 90 * MINUTE:
        return "an hour ago"

    if delta < 24 * HOUR:
        return str(hours) + " hours to go"

    if delta < 48 * HOUR:
        return "yesterday"

    if delta < 30 * DAY:
        return str(days) + " days to go"

    if delta < 12 * MONTH:
        months = delta / MONTH
        if months <= 1:
            return "one month to go"
        else:
            return str(months) + " months to go"
    else:
        years = days / 365.0
        if years <= 1:
            return "one year to go"
        else:
            return f"{float('%.8g' % years)} years to go"


if __name__ == "__main__":
    app()  # pragma: no cover
