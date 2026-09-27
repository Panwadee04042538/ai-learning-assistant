#!/bin/sh
# Railway: รัน dashboard (background) + Discord bot (foreground) ใน service เดียว
# bot เป็นโปรเซสหลัก: ถ้า bot จบ container จะจบและ restart policy ทำงาน
python dashboard_app.py &
exec python main.py
