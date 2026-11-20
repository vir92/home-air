#!/usr/bin/env python3
"""Copy every finished day of ThingSpeak data into data/ so it is kept for good.

GitHub Actions runs this every night (see .github/workflows/archive.yml).
  data/raw/YYYY-MM.csv  every 1-minute reading of that month (India time)
  data/daily.csv        one summary row per day
Days already listed in daily.csv are skipped, so it is safe to run again.
"""
import csv, json, os, urllib.request, datetime as dt

CH, KEY = 3585826, "80QMISM148D3SA9M"          # read-only key (already public in index.html)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, DAILY = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data", "daily.csv")
COLS = ["time", "indoor_aqi", "pm1", "pm25", "pm10", "outdoor_aqi", "outdoor_pm25", "outdoor_temp_c", "outdoor_humidity"]
FIELDS = ["field4", "field1", "field2", "field3", "field5", "field6", "field7", "field8"]
DCOLS = ["date", "readings", "indoor_avg", "indoor_min", "indoor_max", "pm25_avg", "outdoor_avg"]
API = f"https://api.thingspeak.com/channels/{CH}"


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def day_rows(day):
    start = dt.datetime.combine(day, dt.time(), IST).astimezone(dt.timezone.utc)
    end = start + dt.timedelta(days=1, seconds=-1)
    q = lambda t: t.strftime("%Y-%m-%d%%20%H:%M:%S")
    feeds = get(f"{API}/feeds.json?api_key={KEY}&start={q(start)}&end={q(end)}&results=8000")["feeds"]
    rows = []
    for f in feeds:
        t = dt.datetime.fromisoformat(f["created_at"].replace("Z", "+00:00")).astimezone(IST)
        rows.append([t.strftime("%Y-%m-%d %H:%M:%S")] + [f.get(k) or "" for k in FIELDS])
    return rows


def summary(day, rows):
    col = lambda i: [float(r[i]) for r in rows if r[i] != ""]
    ind, pm, out = col(1), col(3), col(5)
    avg = lambda a: f"{sum(a) / len(a):.1f}" if a else ""
    return [day.isoformat(), len(rows), avg(ind), f"{min(ind):.0f}" if ind else "",
            f"{max(ind):.0f}" if ind else "", avg(pm), avg(out)]


def append_raw(rows):
    by_month = {}
    for r in rows:
        by_month.setdefault(r[0][:7], []).append(r)
    for month, new in by_month.items():
        path = os.path.join(RAW, month + ".csv")
        seen = set()
        if os.path.exists(path):
            with open(path) as f:
                seen = {r[0] for r in csv.reader(f)}
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if not seen:
                w.writerow(COLS)
            w.writerows(r for r in new if r[0] not in seen)


def main():
    os.makedirs(RAW, exist_ok=True)
    done = set()
    if os.path.exists(DAILY):
        with open(DAILY) as f:
            done = {r["date"] for r in csv.DictReader(f)}
    first = dt.datetime.fromisoformat(get(f"{API}/feeds.json?api_key={KEY}&results=0")["channel"]["created_at"]
                                      .replace("Z", "+00:00")).astimezone(IST).date()
    today = dt.datetime.now(IST).date()
    day = first
    while day < today:                      # only finished days
        if day.isoformat() not in done:
            rows = day_rows(day)
            append_raw(rows)
            new_file = not os.path.exists(DAILY)
            with open(DAILY, "a", newline="") as f:
                w = csv.writer(f)
                if new_file:
                    w.writerow(DCOLS)
                w.writerow(summary(day, rows))
            print(f"{day}: {len(rows)} readings archived")
        day += dt.timedelta(days=1)


if __name__ == "__main__":
    main()
