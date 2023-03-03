import pymysql
from fastapi import FastAPI

app = FastAPI()


@app.get("/{issue}")
@app.post("/{issue}")
async def root(issue: str):
    if issue == 'favicon.ico':
        return
    with pymysql.connect(host='10.10.20.10',
                         user='service_user',
                         password='12tVPzSr',
                         database='redmine',
                         cursorclass=pymysql.cursors.DictCursor) as connection:
        with connection.cursor() as cursor:
            sql = f"""select custom_field_id, value from custom_values where customized_id = {issue}"""
            cursor.execute(sql)
            data = cursor.fetchall()
            response = {
                'name': None,
                'phone': None,
                'street': None
            }
            street = {}
            if data:
                for item in data:
                    if item['custom_field_id'] == 46:
                        response['name'] = item['value']
                    elif item['custom_field_id'] == 5:
                        response['phone'] = item['value']
                    elif item['custom_field_id'] == 8:
                        street['name'] = item['value']
                    elif item['custom_field_id'] == 10:
                        street['number'] = item['value']
                response['street'] = ' '.join(filter(None, [street.get('name'), street.get('number')])) if street.get('name') and street.get('number') else None
    return response