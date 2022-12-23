FROM python:3.9-alpine

WORKDIR /home/gayazovbr

COPY main.py .
COPY add_user.yql .
COPY create_table.yql .
COPY find_user.yql .
COPY get_names.yql .
COPY update_rating.yql .
COPY token .

RUN apk update && pip install pyTelegramBotAPI && python3 -m pip install ydb && pip install six && \
    pip install packaging

CMD ["python3",  "main.py"]