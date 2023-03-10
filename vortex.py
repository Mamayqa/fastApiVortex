import json
import traceback
import pymysql
import datetime
import hashlib
import logging
import uvicorn
import os

from fastapi import FastAPI, UploadFile, Form, Request, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from pymysql.constants import CLIENT
from typing import Optional, Union


class User(BaseModel):
    id: int
    login: str
    email: str | None = None
    full_name: str
    admin: bool
    roles: str | None = None
    groups: str | None = None
    token: str | None = None
    status: int
    specific_id: int | None = None
    type: str


class UserInDB(User):
    hashed_password: str
    salt: str


TOKEN = os.getenv('BOT_VORTEX_TOKEN')
file_path = os.path.dirname(__file__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.on_event("startup")
async def startup_event():
    if not os.path.exists(file_path + '/files/'):
        os.mkdir(file_path + '/files/')
    if not os.path.exists(file_path + '/logs/'):
        os.mkdir(file_path + '/logs/')
    if not os.path.exists(file_path + '/logs/' + datetime.datetime.now().strftime('%Y') + '/'):
        os.mkdir(file_path + '/logs/' + datetime.datetime.now().strftime('%Y') + '/')
    if not os.path.exists(
            file_path + '/logs/' + datetime.datetime.now().strftime('%Y') + '/' + datetime.datetime.now().strftime(
                '%m') + '/'):
        os.mkdir(file_path + '/logs/' + datetime.datetime.now().strftime('%Y') + '/' + datetime.datetime.now().strftime(
            '%m') + '/')
    if not os.path.exists(file_path + '/report/'):
        os.mkdir(file_path + '/report/')
    logger = logging.getLogger("uvicorn.error")
    handler = logging.handlers.RotatingFileHandler('logs/' + datetime.datetime.now().strftime('%Y') + '/' + datetime.datetime.now().strftime(
        '%m') + '/' + 'error_'+datetime.datetime.now().strftime('%d')+'.log', mode="a", maxBytes=100 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger = logging.getLogger("uvicorn.access")
    handler = logging.handlers.RotatingFileHandler('logs/' + datetime.datetime.now().strftime('%Y') + '/' + datetime.datetime.now().strftime(
        '%m') + '/' + 'access_'+datetime.datetime.now().strftime('%d')+'.log', mode="a", maxBytes=100 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s %(message)s"))
    logger.addHandler(handler)


def get_connection_pymysql():
    """
    ?????????????????????? ?? ???????? ????????????
    :return:
    """
    # connection = pymysql.connect(host='10.10.20.10',
    #                              user='service_user',
    #                              password='12tVPzSr',
    #                              database='redmine',
    # #                              cursorclass=pymysql.cursors.DictCursor)
    # connection = pymysql.connect(host='localhost',
    #                              user='support',
    #                              password='SXUjsdR4',
    #                              database='crm',
    #                              cursorclass=pymysql.cursors.DictCursor,
    #                              client_flag=CLIENT.MULTI_STATEMENTS)
    connection = pymysql.connect(host='10.10.20.129',
                                 user='crm_user',
                                 password='crm_user',
                                 database='crm',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 client_flag=CLIENT.MULTI_STATEMENTS)
    return connection


def get_users(**kwargs):
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""
        select temp2.id,
               temp2.full_name,
               temp2.login,
               temp2.admin,
               temp2.hashed_password,
               temp2.salt,
               temp2.type,
               temp2.name as roles,
               group_concat(u2.id, '/', u2.lastname) as groups,
               temp2.specific_id,
               temp2.status
        from (select temp.id,
                     temp.login,
                     temp.admin,
                     temp.hashed_password,
                     temp.salt,
                     full_name,
                     temp.type,
                     group_concat(name) as name,
                     count,
                     temp.specific_id,
                     status
              from (select u.id,
                           u.login,
                           u.admin,
                           u.hashed_password,
                           u.salt,
                           concat(lastname, ' ', firstname)         as full_name,
                           type,
                           concat(project_id, '/', r.id, '/', name) as name,
                           count(*)                                 as count,
                           u.specific_id,
                           status
                    from users as u
                             left join members m on m.user_id = u.id
                             left join member_roles mr on mr.member_id = m.id
                             left join roles r on r.id = mr.role_id
                    group by u.id, concat(lastname, ' ', firstname), type, name) as temp
              group by temp.id, full_name, temp.type) as temp2
                 left join groups_users gu on temp2.id = gu.user_id
                 left join users u2 on u2.id = gu.group_id
                 {'where temp2.id = ' + str(kwargs.get('user_id')) if kwargs.get('user_id') else "where temp2.login = '" + kwargs.get('login') + "'" if kwargs.get('login') else ''}
        group by temp2.id, full_name, temp2.login"""
            cursor.execute(sql)
            return cursor.fetchall()


users_db = {}
users_active_session = {}
for user in get_users():
    users_db[user['login']] = user


def get_projects(**kwargs):
    """
    ???????????????? ???????????? ????????????????
    :param kwargs:
    :return:
    """
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f""" select projects.id, name from projects
            {f'''join members m on projects.id = m.project_id
            where user_id = {kwargs.get('user_id')}''' if kwargs.get('user_id') else ''}"""
            cursor.execute(sql)
    return cursor.fetchall()


def get_statuses(**kwargs):
    """
    ???????????????? ???????????? ????????????????
    :param kwargs:
    :return:
    """
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f""" select id, name from issue_statuses"""
            cursor.execute(sql)
    return cursor.fetchall()


def get_trackers(**kwargs):
    """
    ???????????????? ???????????? ????????????????
    :param kwargs:
    :return:
    """
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f""" select trackers.id, name {', project_id' if kwargs.get('projects') else ''} from trackers
            {(f'''join projects_trackers pt on trackers.id = pt.tracker_id
            where project_id= ''' + ' or project_id = '.join([str(project['id']) for project in kwargs.get('projects')])) if kwargs.get('projects') else ''}"""
            cursor.execute(sql)
    return cursor.fetchall()


def get_priority(**kwargs):
    """
    ???????????????? ???????????? ??????????????????????
    :param kwargs:
    :return:
    """
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f""" select id, name from enumerations where type = 'IssuePriority'"""
            cursor.execute(sql)
    return cursor.fetchall()


def get_issue(**kwargs):
    user_id = kwargs.get('user_id')
    issue_id = kwargs.get('issue_id')
    search_text = kwargs.get('search_text')
    limit = kwargs.get('limit')
    offset = kwargs.get('offset')
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""
select id,
       tracker,
       project,
       subject,
       done_ratio,
       description,
       responsible,
       status,
       assigned_to_id,
       updated_on,
       created_on,
       icon,
       priority,
       members,
       attachments,
       relations,
       parent_id,
       parent_title,
       parent_status,
       parent_tracker,
       subtasks,
       cfs,
       sl,
       total_tasks,
       group_concat(journal_created_on, '|sep_for_j|', journal_notes, '|sep_for_j|', journal_user_id, '|sep_for_j|',
                    journal_details separator '|____|') as journal
from (select id,
             tracker,
             project,
             subject,
             done_ratio,
             description,
             responsible,
             status,
             assigned_to_id,
             updated_on,
             created_on,
             icon,
             priority,
             members,
             attachments,
             journal_user_id,
             journal_notes,
             journal_created_on,
             parent_id,
             parent_tracker,
             parent_status,
             parent_title,
             subtasks,
             cfs,
             group_concat(sl separator '|!!|') as sl,
             total_tasks,
             concat(ir_issues, '|/|', ir2_issues)   as relations,
             group_concat(property, '|sep_for_jd|', prop_key, '|sep_for_jd|', old_value, '|sep_for_jd|',
                          value separator '|----|') as journal_details
      from (select issues.id                                                                                as id,
                   trackers.name                                                                            as tracker,
                   projects.name                                                                            as project,
                   issues.subject,
                   issues.done_ratio,
                   issues.description,
                   concat(u.lastname, ' ', u.firstname)                                                     as responsible,
                   issue_statuses.name                                                                      as status,
                   issues.assigned_to_id,
                   issues.updated_on,
                   issues.created_on,
                   issues.icon,
                   issues.cfs,
                   issues.total_tasks,
                   e.name                                                                                   as priority,
                   group_concat(distinct issue_members.id, '/', u2.id, '/', u2.lastname, ' ', u2.firstname) as members,
                   group_concat(distinct attachments.id, '|', attachments.filename separator
                                '|////|')                                                                   as attachments,
                   j.created_on                                                                             as journal_created_on,
                   j.user_id                                                                                as journal_user_id,
                   j.notes                                                                                  as journal_notes,
                   j.id                                                                                     as j_id,
                   jd.property,
                   jd.value,
                   jd.old_value,
                   jd.prop_key,
                   parent.id                                                                                as parent_id,
                   parent.subject                                                                           as parent_title,
                   parent_tracker.name                                                                      as parent_tracker,
                   parent_status.name                                                                       as parent_status,
                   concat(stt.name, '|/|', group_concat(s.name, '/|/', s.value, '/|/', s.is_success separator '|#|')) as sl,
                   group_concat(distinct subtasks.id, '/|/', subtasks.subject, '/|/', subtasks_status.name, '/|/',
                                subtasks_tracker.name separator '|/|')                                      as subtasks,
                   group_concat(distinct ir_issues.id, '/|/', ir_issues.subject separator
                                '|/|')                                                                      as ir_issues,
                   group_concat(distinct ir2_issues.id, '/|/', ir2_issues.subject separator
                                '|/|')                                                                      as ir2_issues
            from (select issues.id,
                         issues.tracker_id,
                         project_id,
                         subject,
                         description,
                         status_id,
                         assigned_to_id,
                         priority_id,
                         author_id,
                         created_on,
                         updated_on,
                         done_ratio,
                         parent_id,
                         is_private,
                         closed_on,
                         icon,
                         total_tasks,
                         group_concat(cf.id, '//|//', cf.name, '//|//', cfv.value separator '||/||') as cfs
                  from (select * from(select *, count(*) over () as total_tasks
                        from issues
                        {f'''where (issues.assigned_to_id = {user_id} or issues.assigned_to_id in
                           (select group_id from groups_users where user_id = {user_id}))
                      and issues.status_id != 5 and issues.status_id != 6''' if user_id
            else f'''where issues.id = {issue_id}''' if issue_id
            else f'''where issues.description rlike '{search_text}' or issues.subject rlike '{search_text}' ''' if search_text
            else ''}) as issues
                  {f'''limit {limit} offset {offset}''' if limit and offset else ''}) as issues
                           left join custom_fields_trackers cf_t on issues.tracker_id = cf_t.tracker_id
                           left join custom_fields cf on cf_t.custom_field_id = cf.id
                           left join custom_values cfv
                                     on cf_t.custom_field_id = cfv.custom_field_id and
                                        issues.id = cfv.customized_id
                  group by issues.id) as issues
                     left join users u on u.id = assigned_to_id
                     join enumerations e on issues.priority_id = e.id
                     join trackers on trackers.id = issues.tracker_id
                     join issue_statuses on issue_statuses.id = issues.status_id
                     join projects on projects.id = issues.project_id
                     left join issue_relations ir on ir.issue_from_id = issues.id
                     left join issue_relations ir2 on ir2.issue_to_id = issues.id
                     left join issues ir_issues on ir_issues.id = ir.issue_to_id
                     left join issues ir2_issues on ir2_issues.id = ir2.issue_from_id
                     left join issue_members on issues.id = issue_members.watchable_id
                     left join users u2 on issue_members.user_id = u2.id
                     left join attachments on issues.id = attachments.container_id
                     left join journals j on issues.id = j.journalized_id
                     left join journal_details jd on j.id = jd.journal_id
                     left join issues as subtasks on issues.id = subtasks.parent_id
                     left join trackers subtasks_tracker on subtasks.tracker_id = subtasks_tracker.id
                     left join issue_statuses as subtasks_status on subtasks.status_id = subtasks_status.id
                     left join issues as parent on issues.parent_id = parent.id
                     left join trackers parent_tracker on parent.tracker_id = parent_tracker.id
                     left join issue_statuses as parent_status on parent.status_id = parent_status.id
                     left join subtasks_to_task stt on ir_issues.id = stt.task_id
                     left join subtask s on stt.id = s.subtask_list_id
                     left join subtasks_to_task stt on issues.id = stt.task_id
                     left join subtask s on stt.id = s.subtask_list_id
            group by j.id, issues.id, jd.id) as temp
      group by id, temp.j_id) as temp2
group by id"""
            print(sql)
            cursor.execute(sql)
            return cursor.fetchall()


def get_custom_fields(**kwargs):
    with get_connection_pymysql() as connection:
        with connection.cursor() as cursor:
            sql = f"""select distinct id, name, possible_values, default_value from custom_fields
                 {f'''join custom_fields_trackers cft on custom_fields.id = cft.custom_field_id
                 where tracker_id =  {' or tracker_id = '.join([str(tracker['id']) for tracker in kwargs.get('trackers')])}''' if kwargs.get('trackers') else ''}"""
            cursor.execute(sql)
            data = cursor.fetchall()
            for item in data:
                if item['possible_values'] is not None:
                    item['is_select'] = True

            return data


def get_hashed_password(salt, password):
    temp = hashlib.sha1(bytes(password, encoding='utf8')).hexdigest()
    hashed_password = hashlib.sha1(bytes((salt + temp), encoding='utf8')).hexdigest()
    return hashed_password


def make_token(word):
    token = (UserInDB(**users_db[word]).salt + word).encode('utf-8').hex()
    return token


def decode_token(token):
    user = users_active_session[token] if token in users_active_session else None
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = decode_token(token)
    if not user:
        user = {
            'error': True,
            'error_message': 'Invalid authentication credentials'
        }
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user is UserInDB and current_user.status == 3:
        current_user = {
            'error': True,
            'error_message': 'User is deactivated'
        }
    return current_user


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    response = {
        'error': False,
    }
    user_dict = users_db.get(form_data.username)
    if not user_dict:
        response.update({
            'error': True,
            'error_message': 'Login incorrect'
        })
        return response
    user = UserInDB(**user_dict)
    hashed_password = get_hashed_password(user.salt, form_data.password)
    if not hashed_password == user.hashed_password:
        response.update({
            'error': True,
            'error_message': 'Password incorrect'
        })
        return response
    user.token = make_token(user.login)
    users_active_session[user.token] = user
    response.update({
        'access_token': user.token,
        'current_user': {
            'id': user.id,
            'name': {
                'lastname': user.full_name.split(' ')[0],
                'firstname': user.full_name.split(' ')[1],
            },
            'type': user.type,
            'roles': [{
                'project_id': role.split('/')[0],
                'id': role.split('/')[1],
                'name': role.split('/')[2]
            } for role in user.roles.split(',')] if user.roles else None,
            'specific_id': user.specific_id,
            'status': user.status,
            'is_admin': user.admin,
            'groups': [{
                'id': group.split('/')[0],
                'name': group.split('/')[1]
            } for group in user.groups.split(',')] if user.groups else None,
        }
    })
    return response


@app.post("/")
async def api(current_user: User = Depends(get_current_active_user),
              files: Optional[UploadFile] = None,
              data: str = Form(default=None)):
    files = files if files else []
    request_data = json.loads(data) if data else {}
    if type(current_user) is dict:
        return current_user
    response = {
        'error': False,
        'error_text': '',
        'current_user': {
            'id': current_user.id,
            'name': {
                'lastname': current_user.full_name.split(' ')[0],
                'firstname': current_user.full_name.split(' ')[1],
            },
            'type': current_user.type,
            'roles': [{
                'project_id': role.split('/')[0],
                'id': role.split('/')[1],
                'name': role.split('/')[2]
            } for role in current_user.roles.split(',')] if current_user.roles else None,
            'specific_id': current_user.specific_id,
            'status': current_user.status,
            'is_admin': current_user.admin,
            'groups': [{
                'id': group.split('/')[0],
                'name': group.split('/')[1]
            } for group in current_user.groups.split(',')] if current_user.groups else None,
        }
    }
    try:
        if request_data.get('method') == 'get_task_data':
            if request_data.get('on_page_count') is None:
                response['error'] = True
                response['error_message'] = 'on_page_count is null'
            elif request_data.get('current_page_number') is None:
                response['error'] = True
                response['error_message'] = 'current_page_number is null'
            else:
                tasks = []
                total_tasks = None
                for key, item in enumerate(
                        (get_issue(limit=int(request_data.get('on_page_count')),
                                   offset=int(request_data.get('on_page_count')) * (int(
                                       request_data.get('current_page_number')) - 1),
                                   user_id=request_data.get('user_id')) if request_data.get(
                            'user_id')
                        else get_issue(limit=int(request_data.get('on_page_count')),
                                       offset=int(request_data.get('on_page_count')) * (int(
                                           request_data.get('current_page_number')) - 1),
                                       issue_id=request_data.get('issue_id')) if request_data.get(
                            'issue_id')
                        else get_issue(limit=int(request_data.get('on_page_count')),
                                       offset=int(request_data.get('on_page_count')) * (int(
                                           request_data.get('current_page_number')) - 1),
                                       search_text=request_data.get('search_text')) if request_data.get(
                            'search_text')
                        else get_issue(limit=int(request_data.get('on_page_count')),
                                       offset=int(request_data.get('on_page_count')) * (int(
                                           request_data.get('current_page_number')) - 1)))):
                    total_tasks = item['total_tasks']
                    tasks.append({
                        'number': key,
                        'image_data': item['icon'],
                        'task_id': item['id'],
                        'folder': item['tracker'].strip(),
                        'status': item['status'],
                        'tags': [],
                        'complete': item['done_ratio'],
                        'subject': item['subject'],
                        'date_created': item['created_on'].timestamp(),
                        'date_edited': item['updated_on'].timestamp(),
                        'responsible': item['responsible'].strip() if item['responsible'] else None,
                        'description': item['description'],
                        'parent': {
                            'id': item['parent_id'],
                            'title': item['parent_title'],
                            'status': item['parent_status'],
                            'tracker': item['parent_tracker'],
                        },
                        'total_custom_fields': len(item['cfs'].split('|/|')) if item['cfs'] is not None else None,
                        'custom_fields': [{
                            'id': attachment.split('//|//')[0],
                            'name': attachment.split('//|//')[1],
                            'value': attachment.split('//|//')[2],
                        } for attachment in item['cfs'].split('||/||')] if item['cfs'] is not None else None,
                        'total_actions': len(item['journal'].split('|____|')) if item['journal'] is not None else None,
                        'actions': [{
                            'number': key,
                            'date_created': datetime.datetime.strptime(action.split('|sep_for_j|')[0],
                                                                       '%Y-%m-%d %H:%M:%S').timestamp(),
                            'comment': action.split('|sep_for_j|')[1],
                            'author_id': action.split('|sep_for_j|')[2],
                            'action_details': [{
                                'property': sub_action.split('|sep_for_jd|')[0],
                                'prop_key': sub_action.split('|sep_for_jd|')[1],
                                'old_value': sub_action.split('|sep_for_jd|')[2],
                                'value': sub_action.split('|sep_for_jd|')[3],
                            } for sub_action in action.split('|sep_for_j|')[3].split('|----|')] if
                            action.split('|sep_for_j|')[3] is not None else None
                        } for key, action in enumerate(item['journal'].split('|____|'))] if item['journal'] is not None else None,
                        'total_attachments': len(item['attachments'].split('|////|')) if item['attachments'] is not None else None,
                        'attachments': [{
                            'id': attachment.split('|')[0],
                            'filename': attachment.split('|')[1],
                        } for attachment in item['attachments'].split('|////|')] if item['attachments'] is not None else None,
                        'total_members': len(item['members'].split(',')) if item['members'] is not None else None,
                        'members': [{
                            'member_id': user.split('/')[0],
                            'user_id': user.split('/')[1],
                            'user_name': user.split('/')[2],
                        } for user in item['members'].split(',')] if item['members'] is not None else None,
                        'total_relations': len(item['relations'].split('|/|')) if item['relations'] is not None else None,
                        'relations': [{
                            'task_id': relation.split('/|/')[0],
                            'task_name': relation.split('/|/')[1],
                        } for relation in item['relations'].split('|/|')] if item['relations'] is not None else None,
                        'checkList': [{} for subtask_list in item['sl'].split('')]
                    })
                response.update({
                    'method': 'get_task_data',
                    'data': tasks[0] if request_data.get('issue_id') else {
                        'total_tasks': int(total_tasks),
                        'on_page_count': int(request_data.get('on_page_count')),
                        'current_page_number': int(request_data.get('current_page_number')),
                        'page_count': int(total_tasks) // int(request_data.get('on_page_count')) + 1,
                        'tasks': tasks,
                    }
                })
        elif request_data.get('method') == 'get_info_for_create':
            projects = get_projects(user_id=current_user.id)
            trackers = get_trackers(projects=projects)
            custom_fields = get_custom_fields(trackers=trackers)
            response.update({
                'method': 'get_info_for_create',
                'data': {
                    'auth_token': request_data.get('auth_token'),
                    'projects': projects,
                    'trackers': trackers,
                    'custom_fields': custom_fields,
                    'statuses': get_statuses(),
                    'priorities': get_priority(),
                }})
        elif request_data.get('method') == 'create_task':
            icon = None
            sql_attach = ''
            for file in files:
                if '.' in file.filename:
                    temp = file.filename.split('.')
                else:
                    temp = file.filename
                path = datetime.datetime.now().strftime('%Y') + '/' + datetime.datetime.now().strftime(
                    '%m') + '/'
                if not os.path.exists(
                        'files/' + datetime.datetime.now().strftime(
                            '%Y') + '/') and not os.path.exists('files/' + path):
                    os.mkdir('files/' + datetime.datetime.now().strftime('%Y') + '/')
                    os.mkdir('files/' + path)
                elif os.path.exists('files/' + datetime.datetime.now().strftime(
                        '%Y') + '/') and not os.path.exists('files/' + path):
                    os.mkdir('files/' + path)
                if '.' in file.filename:
                    filename = temp[0] + '____' + datetime.datetime.now().strftime('%d %H:%M:%S') + '.' + temp[
                        1]
                else:
                    filename = temp + '____' + datetime.datetime.now().strftime('%d %H:%M:%S')
                file.save(os.path.join('files/' + path, filename))
                size = os.path.getsize(os.path.join('files/' + path + filename))
                sql_attach += f'''insert into attachments (container_id, filename, disk_filename, filesize, content_type, author_id, created_on, description, disk_directory)
                                                    values ((select id from issues order by id desc limit 1), '{file.filename}', '{filename}', {size}, '{file.content_type}',
                                                    {current_user.id}, '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', '', '{path[:-1]}');'''
            sql_member = f"""insert into issue_members (watchable_id, user_id, performed)
                                values ((select id from issues order by id desc limit 1), {current_user.id}, null);""" if request_data.get(
                'members') else ''
            for member in request_data.get('members'):
                sql_member += f"""insert into issue_members (watchable_id, user_id, performed)
                                values ((select id from issues order by id desc limit 1), {member}, null);"""
            sql_subtasks = ''
            for tasks in request_data.get('subtasks'):
                sql_subtasks += f"insert into subtasks_to_task(task_id, name) values ((select id from issues order by id desc limit 1), '{tasks['name']}');"
                for task in tasks['tasks']:
                    sql_subtasks += f"insert into subtask(subtask_list_id, is_success, value, name) values ((select id from subtasks_to_task order by id desc limit 1), {task['isChecked']}, '{task['value']}', '{task['name']}');"
            sql_cfs = ''
            for cf in request_data.get('custom_fields'):
                sql_cfs += f"""insert into custom_values (customized_id, custom_field_id, value)
                                values((select id from issues order by id desc limit 1), {cf['id']}, '{'/'.join(cf['value']) if type(cf['value']) is list else cf['value']}');"""
            with get_connection_pymysql() as connection:
                with connection.cursor() as cursor:
                    sql = f"""
        insert into issues (tracker_id, project_id, subject, description, status_id, assigned_to_id, priority_id,
                            author_id, created_on, updated_on, done_ratio, parent_id, is_private, closed_on, icon)
        values ({request_data.get('tracker')},
                {request_data.get('project')},
                '{request_data.get('title')}',
                '{request_data.get('description')}',
                {request_data.get('status')},
                {request_data.get('responsible')},
                {request_data.get('priority')},
                {current_user.id},
                '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}',
                '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', 0,
                {request_data.get('parent') if request_data.get('parent') else 'null'},
                {1 if request_data.get('is_private') else 0}, null,
                {"'" + icon + "'" if icon else 'null'});
        {sql_attach}{sql_member}{sql_cfs}{sql_subtasks}
        select id from issues order by id desc limit 1""".replace('None', 'null').replace('\'None\'', 'null')
                    cursor.execute(sql)
                connection.commit()
                task_id = cursor.fetchone()['id']
            response.update({
                'method': 'create_task',
                'data': {
                    'auth_token': request_data.get('auth_token'),
                    'task_id': task_id,
                }
            })
        elif request_data.get('method') == 'edit_task':
            sql_journal_details = ''
            sql_attach = ''
            for file in files:
                if '.' in file.filename:
                    temp = file.filename.split('.')
                else:
                    temp = file.filename
                path = datetime.datetime.now().strftime('%Y') + '/' + datetime.datetime.now().strftime(
                    '%m') + '/'
                if not os.path.exists(
                        'files/' + datetime.datetime.now().strftime(
                            '%Y') + '/') and not os.path.exists('files/' + path):
                    os.mkdir('files/' + datetime.datetime.now().strftime('%Y') + '/')
                    os.mkdir('files/' + path)
                elif os.path.exists('files/' + datetime.datetime.now().strftime(
                        '%Y') + '/') and not os.path.exists('files/' + path):
                    os.mkdir('files/' + path)
                if '.' in file.filename:
                    filename = temp[0] + '____' + datetime.datetime.now().strftime(
                        '%d %H:%M:%S') + '___' + str(random.randint(1, 10000)) + '.' + temp[
                                   1]
                else:
                    filename = temp + '____' + datetime.datetime.now().strftime(
                        '%d %H:%M:%S') + '___' + str(random.randint(1, 10000))
                file.save(os.path.join('files/' + path, filename))
                size = os.path.getsize(os.path.join('files/' + path + filename))
                sql_journal_details += f"insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attachment', (select id from attachments where disk_filename = '{filename}' and disk_directory = '{path[:-1]}'), null, '{file.filename}');"
                sql_attach += f'''insert into attachments (container_id, filename, disk_filename, filesize, content_type, author_id, created_on, description, disk_directory)
                                                                values ((select id from issues order by id desc limit 1), '{file.filename}', '{filename}', {size}, '{file.content_type}',
                                                                {current_user.id}, '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', '', '{path[:-1]}');'''
            sql_attach_del = ''
            for attach in request_data.get('files_to_del'):
                sql_journal_details += f"insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attachment', {attach}, (select filename from attachments where id = {attach}), null);"
                sql_attach_del += f"""delete from attachments where id = {attach};"""
            sql_relations = ''
            sql_journal_relations = ''
            for relation in request_data.get('relations'):
                sql_relations += f"""if (select count(*) from issue_relations
                                            where issue_from_id = {request_data.get('task')} and issue_to_id = {relation}
                                               or issue_from_id = {relation} and issue_to_id = {request_data.get('task')}) < 1 then
                                            insert into issue_relations (issue_from_id, issue_to_id) values ({request_data.get('task')}, {relation}); end if;"""
                sql_journal_details += f"""if (select count(*) from issue_relations
                                            where issue_from_id = {request_data.get('task')} and issue_to_id = {relation}
                                               or issue_from_id = {relation} and issue_to_id = {request_data.get('task')}) > 0 then
                                               insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'relation', 'relates', null, {relation}); end if;"""
                sql_journal_relations += f"""if (select count(*) from issue_relations
                                            where issue_from_id = {request_data.get('task')} and issue_to_id = {relation}
                                               or issue_from_id = {relation} and issue_to_id = {request_data.get('task')}) > 0 then
                                               insert into journals (journalized_id, user_id, notes, created_on) values ({relation}, {current_user.id}, '', '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}');
                                               insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'relation', 'relates', null, {request_data.get('task')});
                                               end if;"""
            sql_relations_to_del = ''
            sql_journal_relations_to_del = ''
            for relation in request_data.get('relations_to_del'):
                sql_relations_to_del += f"""if (select count(*) from issue_relations
                                            where issue_from_id = {request_data.get('task')} and issue_to_id = {relation}
                                               or issue_from_id = {relation} and issue_to_id = {request_data.get('task')}) > 0 then
                                            delete from issue_relations where issue_from_id = {request_data.get('task')} and issue_to_id = {relation}
                                               or issue_from_id = {relation} and issue_to_id = {request_data.get('task')}; end if;"""
                sql_journal_details += f"""if (select count(*) from issue_relations
                                            where issue_from_id = {request_data.get('task')} and issue_to_id = {relation}
                                               or issue_from_id = {relation} and issue_to_id = {request_data.get('task')}) < 1 then
                                               insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'relation', 'relates', {relation}, null); end if;"""
                sql_journal_relations_to_del += f"""if (select count(*) from issue_relations
                                            where issue_from_id = {request_data.get('task')} and issue_to_id = {relation}
                                               or issue_from_id = {relation} and issue_to_id = {request_data.get('task')}) < 1 then
                                               insert into journals (journalized_id, user_id, notes, created_on) values ({relation}, {current_user.id}, '', '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}');
                                               insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'relation', 'relates', {request_data.get('task')}, null); end if;"""
            sql_members_del = ''
            for member in request_data.get('members_to_del'):
                sql_members_del += f"""delete from issue_members where user_id = {member} and watchable_id = {request_data.get('task')};"""
            sql_members = ''
            for member in request_data.get('members'):
                sql_members += f"""insert into issue_members (watchable_id, user_id, performed)
                                values ({request_data.get('task')}, {member}, null) on duplicate key update performed = values(performed);"""
            sql_subtasks = ''
            for tasks in request_data.get('subtasks'):
                sql_subtasks += f"insert into subtasks_to_task(task_id, name) values ((select id from issues order by id desc limit 1), '{tasks['name']}') on duplicate key update name=values(name);"
                for task in tasks['tasks']:
                    sql_subtasks += f"insert into subtask(subtask_list_id, is_success, value, name) values ((select id from subtasks_to_task order by id desc limit 1), {task['isChecked']}, '{task['value']}', '{task['name']}') on duplicate key update is_success=values(is_success), value=values(value);"

            sql_journal_details += f"""if (select count(*) from issue_members where watchable_id = {request_data.get('task')} and (user_id = {' or user_id = '.join(map(str, request_data.get('members')))} or user_id = {current_user.id})) < 1 then insert into journal_details (journal_id, property, prop_key, old_value, value)
                            values ((select id from journals order by id desc limit 1), 'attr', 'issue_mb', (
                            select group_concat(user_id separator '/') from issue_members where watchable_id = {request_data.get('task')} group by watchable_id), '{'/'.join(map(str, request_data.get('members')))}'); end if;""" if request_data.get(
                'members') else ''
            sql_custom_fields = ''
            cfs = []
            for custom_field in request_data.get('custom_fields'):
                cfs.append(custom_field['id'])
                sql_journal_details += f"""if {custom_field['id']} in (select custom_field_id from custom_fields_trackers where tracker_id = (select tracker_id from issues where id = {request_data.get('task')})) and
                            '{'/'.join(custom_field['value']) if type(custom_field['value']) is list else custom_field['value']}' != ifnull((select value from custom_values where customized_id = {request_data['task']} and custom_field_id = {custom_field['id']}),'None') then
                            insert into journal_details (journal_id, property, prop_key, old_value, value)
                            values ((select id from journals order by id desc limit 1), 'cf', {custom_field['id']}, (select value from custom_values where customized_id = {request_data.get('task')} and custom_field_id = {custom_field['id']}), '{'/'.join(custom_field['value']) if type(custom_field['value']) is list else custom_field['value']}'); end if;"""
                sql_custom_fields += f"""insert into custom_values (customized_id, custom_field_id, value)
                                values ({request_data.get('task')}, {custom_field['id']}, '{'/'.join(custom_field['value']) if type(custom_field['value']) is list else custom_field['value']}') on duplicate key update value = values(value);"""
            sql_custom_fields_del = f"delete from custom_values where customized_id = {request_data.get('task')} and custom_field_id !=" + ' and custom_field_id != '.join(
                map(str, cfs))
            with get_connection_pymysql() as connection:
                with connection.cursor() as cursor:
                    sql = f"""insert into journals (journalized_id, user_id, notes, created_on)
                                    values({request_data.get('task')}, {current_user.id}, '{request_data.get('comment') if request_data.get('comment') else ''}', '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}');
                                    {f'''if (select subject from issues where id = {request_data.get('task')}) != '{request_data.get('title')}' then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'subject', (select subject from issues where id = {request_data.get('task')}), '{request_data.get('title')}'); end if;''' if request_data.get('title') else ''}
                                    {f'''if (select tracker_id from issues where id = {request_data.get('task')}) != {request_data.get('tracker')} then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'tracker_id', (select tracker_id from issues where id = {request_data.get('task')}), '{request_data.get('tracker')}'); end if;''' if request_data.get('tracker') else ''}
                                    {f'''if (select project_id from issues where id = {request_data.get('task')}) != {request_data.get('project')} then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'project_id', (select project_id from issues where id = {request_data.get('task')}), '{request_data.get('project')}'); end if;''' if request_data.get('project') else ''}
                                    {f'''if (select description from issues where id = {request_data.get('task')}) != '{request_data.get('description')}' then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'description', (select description from issues where id = {request_data.get('task')}), '{request_data.get('description')}'); end if;''' if request_data.get('description') else ''}
                                    {f'''if (select status_id from issues where id = {request_data.get('task')}) != {request_data.get('status')} then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'status_id', (select status_id from issues where id = {request_data.get('task')}), '{request_data.get('status')}'); end if;''' if request_data.get('status') else ''}
                                    {f'''if (select assigned_to_id from issues where id = {request_data.get('task')}) != {request_data.get('responsible')} then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'assigned_to_id', (select assigned_to_id from issues where id = {request_data.get('task')}), '{request_data.get('responsible')}'); end if;''' if request_data.get('responsible') else ''}
                                    {f'''if (select priority_id from issues where id = {request_data.get('task')}) != {request_data.get('priority')} then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'priority_id', (select priority_id from issues where id = {request_data.get('task')}), '{request_data.get('priority')}'); end if;''' if request_data.get('priority') else ''}
                                    {f'''if (select is_private from issues where id = {request_data.get('task')}) != {request_data.get('is_private')} then insert into journal_details (journal_id, property, prop_key, old_value, value) values ((select id from journals order by id desc limit 1), 'attr', 'is_private', (select is_private from issues where id = {request_data.get('task')}), '{request_data.get('is_private')}'); end if;''' if request_data.get('is_private') else ''}
                                    update issues set updated_on = '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'
                                        {f''', subject = "{request_data.get('title')}"''' if 'title' in request_data.keys() else ''}
                                        {f''', tracker_id = {request_data.get('tracker')}''' if 'tracker' in request_data.keys() else ''}
                                        {f''', project_id = {request_data.get('project')}''' if 'project' in request_data.keys() else ''}
                                        {f''', description = "{request_data.get('description')}"''' if 'description' in request_data.keys() else ''}
                                        {f''', status_id = {request_data.get('status')}''' if 'status' in request_data.keys() else ''}
                                        {f''', assigned_to_id = {request_data.get('responsible')}''' if 'responsible' in request_data.keys() else ''}
                                        {f''', priority_id = {request_data.get('priority')}''' if 'priority' in request_data.keys() else ''}
                                        {f''', is_private = {request_data.get('is_private')}''' if 'is_private' in request_data.keys() else ''}
                                        where id = {request_data.get('task')};{sql_attach}{sql_relations}{sql_relations_to_del}
                                        {sql_journal_details}
                                        {sql_attach_del}{sql_members_del}{sql_members}{sql_custom_fields}{sql_subtasks}{sql_custom_fields_del if request_data.get('custom_fields') else ''};
                                        if (select count(*) as count from journal_details where journal_id = (select id from journals order by id desc limit 1)) < 1 and
               (select notes from journals where id = (select id from journals order by id desc limit 1)) in ('', null) then
        delete from journals where id = (select id from journals order by id desc limit 1);end if;{sql_journal_relations}{sql_journal_relations_to_del}
    """
                    cursor.execute(sql)
                connection.commit()
            response.update({
                'method': 'edit_task',
                'data': {
                    'auth_token': request_data.get('auth_token'),
                    'task': request_data.get('task')
                }
            })
        elif request_data.get('method') == 'get_duty':
            with get_connection_pymysql() as connection:
                with connection.cursor() as cursor:
                    sql = f"""select id from naryad_director where user_id = {current_user.id} and status = 1"""
                    cursor.execute(sql)
                    data = cursor.fetchone()
                    if data:
                        sql = f"""select * from naryads where naryad_for = {data['id']}"""
                        cursor.execute(sql)
                        works = []
                        for item in cursor.fetchall():
                            works.append({
                                'task': item['issue_id'],
                                'responsible': item['assigned'],
                                'comment': item['comment_id'],
                            })
                        response.update({
                            'method': 'get_work',
                            'data': {
                                'works': works
                            }
                        })
                    else:
                        response.update({
                            'error': True,
                            'error_message': 'You do not have permissions',
                            'method': 'get_work',
                            'data': {
                            }
                        })
                    # sql = f"""insert into naryads (date, issue_id, naryad_for)
                    # values ('{request_data.get('work_date')}', {request_data.get('task')}, {request_data.get('worker_id')})"""
                    # cursor.execute(sql)
                connection.commit()
        elif request_data.get('method') == 'create_work':
            with get_connection_pymysql() as connection:
                with connection.cursor() as cursor:
                    sql = f"""insert into naryads (date, issue_id, naryad_for)
                                values ('{request_data.get('work_date')}', {request_data.get('task')}, {request_data.get('worker_id')})"""
                    cursor.execute(sql)
                connection.commit()
            response.update({
                'method': 'create_work',
                'data': {
                }
            })
        elif request_data.get('method') == 'delete_work':
            with get_connection_pymysql() as connection:
                with connection.cursor() as cursor:
                    sql = f"""delete from naryads where date = '{request_data.get('work_date')}'
                                and issue_id = {request_data.get('task')}
                                and naryad_for = {request_data.get('worker_id')}"""
                    cursor.execute(sql)
                connection.commit()
            response.update({
                'method': 'delete_work',
                'data': {
                }
            })
        elif request_data.get('method') == 'distribute_work':
            with get_connection_pymysql() as connection:
                with connection.cursor() as cursor:
                    sql = f"""insert into journals (journalized_id, user_id, notes, created_on)
                                values ('{request_data.get('task')}', {current_user.id}, '{request_data.get('comment')}', '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}');
                                insert into journal_details (journal_id, property, prop_key, old_value, value)
                                values (
                                (select id from journals where created_on = '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}' and journalized_id = {request_data.get('task')} and user_id = {current_user.id}),
                                 'attr', 'assigned_to_id', (select assigned_to_id from issues where id = {request_data.get('task')}),
                                  '{request_data.get('user_id')}');
                                insert into journal_details (journal_id, property, prop_key, old_value, value)
                                values (
                                (select id from journals where created_on = '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}' and journalized_id = {request_data.get('task')} and user_id = {current_user.id}),
                                 'attr', 'assigned_to_id', (select assigned_to_id from issues where id = {request_data.get('task')}),
                                  '{request_data.get('user_id')}');
                                update issues set assigned_to_id = {request_data.get('user_id')} where id = {request_data.get('task')};
                                update naryads set comment_id=(
                                select id from journals where created_on = '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}' and journalized_id = {request_data.get('task')} and user_id = {current_user.id}),
                                 assigned = {request_data.get('user_id')}
                                 where issue_id = {request_data.get('task')} and
                                 date = '{request_data.get('date')}' and
                                 (naryad_for = {' or naryad_for = '.join(current_user['director_id'].split(','))});"""
                    cursor.execute(sql)
                connection.commit()
            response.update({
                'method': 'distribute_work',
                'data': {
                }
            })
        elif request_data.get('method') == 'delete_work_distribution':
            with get_connection_pymysql() as connection:
                with connection.cursor() as cursor:
                    sql = f"""update naryads set assigned = null where issue_id = {request_data.get('id')} and assigned = {request_data.get('user')} and date = '{request_data.get('date')}'"""
                    cursor.execute(sql)
                connection.commit()
            response.update({
                'method': 'delete_work_distribution',
                'data': {
                }
            })
        elif request_data.get('method') == 'get_info_for_admin':
            if current_user.admin == 1:
                users, roles, cfs, projects, trackers, work_directors, work_managers = [], [], [], [], [], [], []
                for user in get_users():
                    users.append({
                        'user_id': user['id'],
                        'user_name': {
                            'lastname': user['fullname'].split(' ')[0],
                            'firstname': user['fullname'].split(' ')[1],
                        },
                        'user_type': user['type'],
                        'user_roles': [{
                            'project_id': item.split('/')[0],
                            'role_id': item.split('/')[1],
                            'role_name': item.split('/')[2]
                        } for item in user['name'].split(',')] if user['name'] else None,
                        'user_specific_id': user['specific_id'],
                        'user_status': user['status'],
                        'is_admin': user['admin'],
                        'user_groups': [{
                            'group_id': item.split('/')[0],
                            'group_name': item.split('/')[1],
                        } for item in user['groupname'].split(',')] if
                        user['groupname'] else None,
                    })
                with get_connection_pymysql() as connection:
                    with connection.cursor() as cursor:
                        sql = f"""select * from custom_fields"""
                        cursor.execute(sql)
                        for custom_field in cursor.fetchall():
                            cfs.append({
                                'id': custom_field['id'],
                                'name': custom_field['name'],
                                'possible_values': [value for value in
                                                    custom_field['possible_values'].split('\n- ')] if
                                custom_field['possible_values'] else None,
                                'default_value': custom_field['default_value'] if custom_field[
                                    'default_value'] else custom_field['possible_values'].split('\n- ')[0] if
                                custom_field['possible_values'] else None,
                            })
                        sql = f"""select trackers.id, trackers.name, group_concat(cf.id, '|_|', cf.name, '|_|', cf.possible_values, '|_|', cf.default_value separator '|__|') as cfs
                                            from trackers
                                                     left join custom_fields_trackers cft on trackers.id = cft.tracker_id
                                                        left join custom_fields cf on cft.custom_field_id = cf.id
                                            group by trackers.id"""
                        cursor.execute(sql)
                        for tracker in cursor.fetchall():
                            trackers.append({
                                'id': tracker['id'],
                                'name': tracker['name'],
                                'custom_fields': [{
                                    'id': custom_field.split('|_|')[0],
                                    'name': custom_field.split('|_|')[1],
                                    'possible_values': [value for value in
                                                        custom_field.split('|_|')[2].split('\n- ')],
                                    'default_value': custom_field.split('|_|')[3],
                                } for custom_field in tracker['cfs'].split('|__|')] if tracker['cfs'] else None,
                            })
                        sql = f"""select projects.id, projects.name, group_concat(t.id,'|_|', t.name separator '|__|') as trackers
                                            from projects
                                                     left join projects_trackers pt on projects.id = pt.project_id
                                                     left join trackers t on pt.tracker_id = t.id
                                            group by id"""
                        cursor.execute(sql)
                        for project in cursor.fetchall():
                            projects.append({
                                'id': project['id'],
                                'name': project['name'],
                                'trackers': [{
                                    'id': tracker.split('|_|')[0],
                                    'name': tracker.split('|_|')[1]
                                } for tracker in project['trackers'].split('|__|')]
                            })
                        sql = f"""select * from roles"""
                        cursor.execute(sql)
                        for role in cursor.fetchall():
                            roles.append({
                                'id': role['id'],
                                'name': role['name']
                            })
                        sql = f"""select naryad_director.id,
                                                   naryad_director.name,
                                                   naryad_director.status,
                                                   concat(u.id, '|_|', u.lastname, ' ', u.firstname) as user
                                            from naryad_director
                                                     left join users u on u.id = naryad_director.user_id
                                            group by naryad_director.id"""
                        cursor.execute(sql)
                        for nd in cursor.fetchall():
                            work_directors.append({
                                'id': nd['id'],
                                'name': nd['name'],
                                'status': nd['status'],
                                'user': {
                                    'id': nd['user'].split('|_|')[0],
                                    'name': nd['user'].split('|_|')[1],
                                }
                            })
                        sql = f"""select users.id, concat(lastname, ' ', firstname) as name
                                            from users
                                                     left join members m on users.id = m.user_id
                                                     left join member_roles mr on m.id = mr.member_id
                                            where role_id = 1"""
                        cursor.execute(sql)
                        for user in cursor.fetchall():
                            work_managers.append({
                                'id': user['id'],
                                'name': user['roles'],
                            })
                response.update({
                    'method': 'get_info_for_admin',
                    'data': {
                        'total__users': len(users),
                        'on_page_count': request_data.get('on_page_count'),
                        'current_page_number': request_data.get('current_page_number'),
                        'page_count': len(users) // int(request_data.get('on_page_count')) + 1,
                        'users': users,
                        'custom_fields': cfs,
                        'trackers': trackers,
                        'projects': projects,
                        'roles': roles,
                        'work_directors': work_directors,
                        'work_managers': work_managers,
                    }
                })
            else:
                response.update({
                    'error': True,
                    'error_message': 'You are not an administrator',
                    'method': 'get_info_for_admin',
                    'data': {
                    }
                })
        elif request_data.get('method') == 'edit_users':
            if current_user.admin == 1:
                if request_data.get('login') is not None and request_data.get('password') is not None:
                    salt = hashlib.pbkdf2_hmac('sha256', request_data.get('login').encode(), os.urandom(32),
                                               10000).hex()[32:]
                    hashed_password = get_hashed_password(salt=salt, password=request_data.get('password'))
                sql = f"""insert into users ({'id, ' if request_data.get('id') is not None else ''} login, hashed_password, firstname, lastname, admin, status, last_login_on, created_on, updated_on, type, mail_notification, salt, must_change_passwd, passwd_changed_on, specific_id)
                        values ({str(request_data.get('id')) + ',' if request_data.get('id') is not None else ''}
                                '{request_data.get('login') if request_data.get('login') is not None else ''}',
                                '{hashed_password if request_data.get('password') is not None else ''}',
                                '{request_data.get('firstname') if request_data.get('firstname') is not None else ''}',
                                '{request_data.get('lastname')}',
                                {'0' if request_data.get('admin') is None else '1'},
                                {request_data.get('status') if request_data.get('status') is not None else 1}, null,
                                '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}',
                                '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}',
                                '{'Group' if request_data.get('type') else 'User'}',
                                '{request_data.get('mail_notification') if request_data.get('mail_notification') is not None else ''}',
                                {'"' + salt + '"' if request_data.get('password') is not None else 'null'}, 0,
                                '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}',
                                {request_data.get('specific_id') if request_data.get('specific_id') is not None else 'null'})
                                on duplicate key update firstname = values(firstname),
                                lastname = values(lastname),
                                admin = values(admin),
                                status = values(status),
                                updated_on = values(updated_on),
                                mail_notification = values(mail_notification);
                                delete from groups_users where user_id ={request_data.get('id') if request_data.get('id') else '(select id from users order by id desc limit 1)'};
                                delete member_roles from member_roles join members m on m.id = member_roles.member_id where user_id = {request_data.get('id') if request_data.get('id') else '(select id from users order by id desc limit 1)'};
                                delete from members where user_id = {request_data.get('id') if request_data.get('id') else '(select id from users order by id desc limit 1)'};"""
                for group in request_data.get('groups'):
                    sql += f"""insert into groups_users (group_id, user_id) values ({group}, {request_data.get('id') if request_data.get('id') else '(select id from users order by id desc limit 1)'});"""
                for member in request_data.get('members'):
                    sql += f"""insert into members (user_id, project_id, created_on, mail_notification)
                                values ({request_data.get('id') if request_data.get('id') else '(select id from users order by id desc limit 1)'}, {member['project']}, '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}', 0);"""
                    for role in member['roles']:
                        sql += f"""insert into member_roles (member_id, role_id) values ((select id from members order by id desc limit 1), {role});"""
                with get_connection_pymysql() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(sql)
                    connection.commit()
                response.update({
                    'method': 'edit_users',
                    'data': {
                    }
                })
            else:
                response.update({
                    'error': True,
                    'error_message': 'You are not an administrator',
                    'method': 'edit_users',
                    'data': {
                    }
                })
        elif request_data.get('method') == 'edit_custom_field':
            if current_user.admin == 1:
                with get_connection_pymysql() as connection:
                    with connection.cursor() as cursor:
                        sql = f"""insert into custom_fields (name, possible_values, default_value)
                                    values ('{request_data.get('cf_name')}', """ + (
                            '"' + ('\n- '.join(request_data.get('possible_values'))) + '"' if
                            request_data.get(
                                'possible_values') != [] else 'null') + f""", '{request_data.get('default_value') if request_data.get('default_value') else ''}')
                                    on duplicate key update possible_values = values(possible_values), default_value = values(default_value)""" if request_data.get(
                            'possible_values') != [] and request_data.get(
                            'default_value') is not None else f"""delete from custom_fields where name = '{request_data.get('cf_name')}'"""
                        cursor.execute(sql)
                    connection.commit()
                response.update({
                    'method': 'edit_custom_field',
                    'data': {
                    }
                })
            else:
                response.update({
                    'error': True,
                    'error_message': 'You are not an administrator',
                    'method': 'edit_custom_field',
                    'data': {
                    }
                })
        elif request_data.get('method') == 'edit_trackers':
            if current_user.admin == 1:
                with get_connection_pymysql() as connection:
                    with connection.cursor() as cursor:
                        sql = f"""{f'''insert into trackers (name) values ('{request_data.get('tracker_name')}');''' if request_data.get('tracker_name') else ''}
                                    delete from custom_fields_trackers where tracker_id = {request_data.get('tracker') if request_data.get('tracker') else '(select id from trackers order by id desc limit 1)'};
                                    {''.join([f'''insert into custom_fields_trackers (custom_field_id, tracker_id)
                            values ({cf}, {request_data.get('tracker') if request_data.get('tracker') else '(select id from trackers order by id desc limit 1)'});'''
                                              for cf in request_data.get('cfs')]) if request_data.get('cfs') else ''}""" if request_data.get(
                            'tracker_name') and request_data.get('cfs') or request_data.get(
                            'tracker_name') or request_data.get('tracker') and request_data.get('cfs') else f'''
                                        delete from custom_values where customized_id in (select id from issues where tracker_id = {request_data.get('tracker')});
                                        update issues set tracker_id = 1 where tracker_id = {request_data.get('tracker')};
                                        delete from custom_fields_trackers where tracker_id = {request_data.get('tracker')};
                                        delete from projects_trackers where tracker_id = {request_data.get('tracker')};
                                        delete from trackers where id = {request_data.get('tracker')};'''
                        cursor.execute(sql)
                    connection.commit()
                response.update({
                    'method': 'edit_trackers',
                    'data': {
                    }
                })
            else:
                response.update({
                    'error': True,
                    'error_message': 'You are not an administrator',
                    'method': 'edit_trackers',
                    'data': {
                    }
                })
        elif request_data.get('method') == 'edit_roles':
            if current_user.admin == 1:
                with get_connection_pymysql() as connection:
                    with connection.cursor() as cursor:
                        sql = f"insert into roles (name) values ('{request_data.get('role_name')}');" if not request_data.get(
                            'role') and request_data.get(
                            'role_name') else f"update roles set name = '{request_data.get('role_name')}' where id = {request_data.get('role')}" if request_data.get(
                            'role') and request_data.get(
                            'role_name') else f"delete from roles where id = {request_data.get('role')}"
                        cursor.execute(sql)
                    connection.commit()
                response.update({
                    'method': 'edit_roles',
                    'data': {
                    }
                })
            else:
                response.update({
                    'error': True,
                    'error_message': 'You are not an administrator',
                    'method': 'edit_roles',
                    'data': {
                    }
                })
        elif request_data.get('method') == 'edit_projects':
            if current_user.admin == 1:
                with get_connection_pymysql() as connection:
                    with connection.cursor() as cursor:
                        sql = f"insert into projects (name) values ('{request_data.get('project_name')}');" if not request_data.get(
                            'project') and request_data.get(
                            'project_name') else f"update projects set name = '{request_data.get('project_name')}' where id = {request_data.get('project')}" if request_data.get(
                            'project') and request_data.get(
                            'project_name') else f"delete from projects where id = {request_data.get('project')}"
                        cursor.execute(sql)
                    connection.commit()
                response.update({
                    'method': 'edit_projects',
                    'data': {
                    }
                })
            else:
                response.update({
                    'error': True,
                    'error_message': 'You are not an administrator',
                    'method': 'edit_projects',
                    'data': {
                    }
                })
        elif request_data.get('method') == 'edit_workers':
            if current_user.admin == 1:
                with get_connection_pymysql() as connection:
                    with connection.cursor() as cursor:
                        sql = (f"""insert into naryad_director ({'id,' if request_data.get('worker') else ''} name, user_id, status)
                        values ({str(request_data.get('worker')) + ',' if request_data.get('worker') else ''}
                        '{request_data.get('worker_name')}',
                        {request_data.get('user')},
                        {request_data.get('status') if request_data.get('status') else 1})
                        on duplicate key update name=values(name), user_id=values(user_id), status=values(status);""" if request_data.get(
                            'worker_name') or request_data.get('user') or request_data.get(
                            'status') else f"delete from naryad_director where id = {request_data.get('worker')};") + "update users set specific_id = null where specific_id = 3;" + "".join(
                            [f"update users set specific_id = 3 where id = {manager};" for manager in
                             request_data.get(
                                 'work_manager')])
                        cursor.execute(sql)
                    connection.commit()
                response.update({
                    'method': 'edit_workers',
                    'data': {
                    }
                })
            else:
                response.update({
                    'error': True,
                    'error_message': 'You are not an administrator',
                    'method': 'edit_workers',
                    'data': {
                    }
                })
        else:
            response.update({
                'error': True,
                'error_message': 'Invalid method',
                'data': {
                }
            })
    except Exception as e:
        response['error'] = True
        response['error_message'] = 'Critical error'
        response['traceback'] = traceback.format_exc()

    return response


@app.get("/", response_class=HTMLResponse)
async def main():
    with open('static/html/index.html', 'r') as file:
        content = file.read()
    return HTMLResponse(content=content, status_code=200)


@app.get("/error")
async def error():
    return 1 / 0


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse('static/favicon.png')


@app.get('/klard')
@app.post('/klard')
async def klard(street: str = '',
                locality: str = '',
                city: str = '',
                area: str = '',
                region: str = ''):
    all_answers = []
    with pymysql.connect(host='10.10.20.129',
                                 user='klard',
                                 password='klard_password',
                                 database='klard',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 client_flag=CLIENT.MULTI_STATEMENTS) as connection:
        with connection.cursor() as cursor:
            sql = f"""
    select street.name as street, r_main.name as region 
    from street
             left join regions_to_all r on street.id = r.street
             left join region r_main on r.region = r_main.id
    where street.name rlike '{street}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['region']:
                    all_answers.append(item)
            sql = f"""
    select street.name as street, a_main.name as area, r_main.name as region
    from street
             left join areas_to_all a on street.id = a.street
             left join area a_main on a.area = a_main.id         
             left join regions_to_all ra on a.area = ra.area
             left join region r_main on ra.region = r_main.id
    where street.name rlike '{street}' and a_main.name rlike '{area}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['region'] and item['area']:
                    all_answers.append(item)
            sql = f"""
    select street.name as street, c_main.name as city, a_main.name as area, r_main.name as region
    from street
             left join city_to_all c on street.id = c.street
             left join city c_main on c.city = c_main.id
             left join areas_to_all ca on c.city = ca.city
             left join area a_main on ca.area = a_main.id
             left join regions_to_all rca on ca.area = rca.area
             left join region r_main on rca.region = r_main.id
    where street.name rlike '{street}' and c_main.name rlike '{city}' and a_main.name rlike '{area}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['area'] and item['city']:
                    all_answers.append(item)
            sql = f"""
    select street.name as street, c_main.name as city, r_main.name as region
    from street
             left join city_to_all c on street.id = c.street
             left join city c_main on c.city = c_main.id
             left join regions_to_all rc on c.city = rc.city
             left join region r_main on rc.region = r_main.id
    where street.name rlike '{street}' and c_main.name rlike '{city}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['region'] and item['city']:
                    all_answers.append(item)
            sql = f"""
    select street.name as street, o_main.name as object, c_main.name as city, a_main.name as area, r_main.name as region
    from street
             left join objects_to_all o on street.id = o.street
             left join object o_main on o.object = o_main.id
             left join city_to_all oc on o.object = oc.object
             left join city c_main on oc.city = c_main.id
             left join areas_to_all oca on oc.city = oca.city
             left join area a_main on oca.area = a_main.id
             left join regions_to_all roca on oca.area = roca.area
             left join region r_main on roca.region = r_main.id
    where street.name rlike '{street}' and o_main.name rlike '{locality}' and c_main.name rlike '{city}' and a_main.name rlike '{area}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['region'] and item['area'] and item['city'] and item['object']:
                    all_answers.append(item)
            sql = f"""
    select street.name as street, o_main.name as object, a_main.name as area, r_main.name as region
    from street
             left join objects_to_all o on street.id = o.street
             left join object o_main on o.object = o_main.id
             left join areas_to_all oa on o.object = oa.object
             left join area a_main on oa.area = a_main.id
             left join regions_to_all roa on oa.area = roa.area
             left join region r_main on roa.region = r_main.id
    where street.name rlike '{street}' and o_main.name rlike '{locality}' and a_main.name rlike '{area}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['region'] and item['area'] and item['object']:
                    all_answers.append(item)
            sql = f"""
    select street.name as street, o_main.name as object, c_main.name as city, r_main.name as region
    from street
             left join objects_to_all o on street.id = o.street
             left join object o_main on o.object = o_main.id
             left join city_to_all oc on o.object = oc.object
             left join city c_main on oc.city = c_main.id
             left join regions_to_all roc on oc.city = roc.city
             left join region r_main on roc.region = r_main.id
    where street.name rlike '{street}' and o_main.name rlike '{locality}' and c_main.name rlike '{city}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['region'] and item['city'] and item['object']:
                    all_answers.append(item)
            sql = f"""
    select street.name as street, o_main.name as object, r_main.name as region
    from street
             left join objects_to_all o on street.id = o.street
             left join object o_main on o.object = o_main.id
             left join regions_to_all ro on o.object = ro.object
             left join region r_main on ro.region = r_main.id
    where street.name rlike '{street}' and o_main.name rlike '{locality}' and r_main.name rlike '{region}'"""
            cursor.execute(sql)
            for item in cursor.fetchall():
                if item['region'] and item['object']:
                    all_answers.append(item)
            temp = []
            for item in all_answers:
                if area != '' and 'area' in item.keys():
                    temp.append(item)
                elif city != '' and 'city' in item.keys():
                    temp.append(item)
                elif area == '' and city == '':
                    temp.append(item)
            all_answers = temp
    return all_answers
