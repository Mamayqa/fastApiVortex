from sqlalchemy import create_engine, BigInteger, Column, Date, DateTime, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.orm import relationship, declarative_base, Session

engine = create_engine("mysql+pymysql://crm_user:crm_user@10.10.20.129/crm?charset=utf8mb4")


Base = declarative_base()
metadata = Base.metadata


class Attachment(Base):
    __tablename__ = 'attachments'

    id = Column(Integer, primary_key=True)
    container_id = Column(ForeignKey('issues.id'), index=True)
    container_type = Column(String(30))
    filename = Column(String(255))
    disk_filename = Column(String(255))
    filesize = Column(BigInteger)
    content_type = Column(String(255))
    author_id = Column(ForeignKey('users.id'), index=True)
    created_on = Column(DateTime)
    description = Column(String(255))
    disk_directory = Column(String(255))

    author = relationship('User')
    container = relationship('Issue')


class CustomField(Base):
    __tablename__ = 'custom_fields'

    id = Column(Integer, primary_key=True)
    name = Column(String(30), unique=True)
    possible_values = Column(String)
    default_value = Column(String)

    trackers = relationship('Tracker', secondary='custom_fields_trackers')


t_custom_fields_trackers = Table(
    'custom_fields_trackers', metadata,
    Column('custom_field_id', ForeignKey('custom_fields.id'), index=True),
    Column('tracker_id', ForeignKey('trackers.id'), index=True)
)


class CustomValue(Base):
    __tablename__ = 'custom_values'
    __table_args__ = (
        Index('custom_values_pk', 'customized_id', 'custom_field_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    customized_id = Column(ForeignKey('issues.id'), index=True)
    custom_field_id = Column(ForeignKey('custom_fields.id'), index=True)
    value = Column(String)

    custom_field = relationship('CustomField')
    customized = relationship('Issue')


t_email_addresses = Table(
    'email_addresses', metadata,
    Column('id', Integer),
    Column('user_id', ForeignKey('users.id'), index=True),
    Column('address', String(255)),
    Column('is_default', Integer),
    Column('notify', Integer),
    Column('created_on', DateTime),
    Column('updated_on', DateTime)
)


class Enumeration(Base):
    __tablename__ = 'enumerations'

    id = Column(Integer, primary_key=True)
    name = Column(String(30))
    position = Column(Integer)
    is_default = Column(Integer)
    type = Column(String(255))
    active = Column(Integer)
    project_id = Column(Integer)
    parent_id = Column(Integer)
    position_name = Column(String(30))


t_favorite_nfm = Table(
    'favorite_nfm', metadata,
    Column('favorite_id', ForeignKey('users.id'), index=True),
    Column('favorite_by', ForeignKey('users.id'), index=True)
)


t_groups_users = Table(
    'groups_users', metadata,
    Column('group_id', ForeignKey('users.id')),
    Column('user_id', ForeignKey('users.id'), index=True),
    Index('groups_users_pk', 'group_id', 'user_id', unique=True)
)


class IssueMember(Base):
    __tablename__ = 'issue_members'
    __table_args__ = (
        Index('issue_members_pk', 'watchable_id', 'user_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    watchable_type = Column(String(255))
    watchable_id = Column(ForeignKey('issues.id'))
    user_id = Column(ForeignKey('users.id'), index=True)
    performed = Column(Integer)

    user = relationship('User')
    watchable = relationship('Issue')


t_issue_relations = Table(
    'issue_relations', metadata,
    Column('issue_from_id', ForeignKey('issues.id'), index=True),
    Column('issue_to_id', ForeignKey('issues.id'), index=True)
)


class IssueStatus(Base):
    __tablename__ = 'issue_statuses'

    id = Column(Integer, primary_key=True)
    name = Column(String(30))


class Issue(Base):
    __tablename__ = 'issues'

    id = Column(Integer, primary_key=True)
    tracker_id = Column(ForeignKey('trackers.id'), index=True)
    project_id = Column(ForeignKey('projects.id'), index=True)
    subject = Column(String(255))
    description = Column(String)
    status_id = Column(ForeignKey('issue_statuses.id'), index=True)
    assigned_to_id = Column(String(255))
    priority_id = Column(ForeignKey('enumerations.id'), index=True)
    author_id = Column(ForeignKey('users.id'), index=True)
    created_on = Column(DateTime)
    updated_on = Column(DateTime)
    done_ratio = Column(Integer)
    parent_id = Column(ForeignKey('issues.id'), index=True)
    is_private = Column(Integer)
    closed_on = Column(DateTime)
    icon = Column(Text)

    author = relationship('User')
    parent = relationship('Issue', remote_side=[id])
    priority = relationship('Enumeration')
    project = relationship('Project')
    status = relationship('IssueStatus')
    tracker = relationship('Tracker')
    issue_tos = relationship(
        'Issue',
        secondary='issue_relations',
        primaryjoin='Issue.id == issue_relations.c.issue_from_id',
        secondaryjoin='Issue.id == issue_relations.c.issue_to_id'
    )


class JournalDetail(Base):
    __tablename__ = 'journal_details'

    id = Column(Integer, primary_key=True)
    journal_id = Column(ForeignKey('journals.id'), index=True)
    property = Column(String(30))
    prop_key = Column(String(30))
    old_value = Column(String)
    value = Column(String)

    journal = relationship('Journal')


class Journal(Base):
    __tablename__ = 'journals'

    id = Column(Integer, primary_key=True)
    journalized_id = Column(ForeignKey('issues.id'), index=True)
    user_id = Column(ForeignKey('users.id'), index=True)
    notes = Column(String)
    created_on = Column(DateTime)

    journalized = relationship('Issue')
    user = relationship('User')


class MemberRole(Base):
    __tablename__ = 'member_roles'
    __table_args__ = (
        Index('member_roles_pk', 'member_id', 'role_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    member_id = Column(ForeignKey('members.id'), index=True)
    role_id = Column(ForeignKey('roles.id'), index=True)

    member = relationship('Member')
    role = relationship('Role')


class Member(Base):
    __tablename__ = 'members'
    __table_args__ = (
        Index('members_pk', 'project_id', 'user_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), index=True)
    project_id = Column(ForeignKey('projects.id'), index=True)
    created_on = Column(DateTime)
    mail_notification = Column(Integer)

    project = relationship('Project')
    user = relationship('User')


class NaryadDirector(Base):
    __tablename__ = 'naryad_director'

    id = Column(Integer, primary_key=True)
    name = Column(Text)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    status = Column(Integer, nullable=False)

    user = relationship('User')


class Naryad(Base):
    __tablename__ = 'naryads'
    __table_args__ = (
        Index('naryads_pk', 'date', 'issue_id', 'naryad_for', unique=True),
    )

    date = Column(Date, nullable=False)
    issue_id = Column(ForeignKey('issues.id'), nullable=False, index=True)
    assigned = Column(ForeignKey('users.id'), index=True)
    naryad_for = Column(ForeignKey('naryad_director.id'), nullable=False, index=True)
    id = Column(Integer, primary_key=True)
    comment_id = Column(ForeignKey('journals.id'), index=True)

    user = relationship('User')
    comment = relationship('Journal')
    issue = relationship('Issue')
    naryad_director = relationship('NaryadDirector')


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    description = Column(String)
    is_public = Column(Integer)

    trackers = relationship('Tracker', secondary='projects_trackers')


t_projects_trackers = Table(
    'projects_trackers', metadata,
    Column('project_id', ForeignKey('projects.id'), index=True),
    Column('tracker_id', ForeignKey('trackers.id'), index=True)
)


class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String(30))
    issues_visibility = Column(String(30))
    users_visibility = Column(String(30))
    permitions = Column(Text)


t_service_vortex_links = Table(
    'service_vortex_links', metadata,
    Column('service_user_id', Integer),
    Column('vortex_user_id', ForeignKey('users.id')),
    Index('table_name_pk', 'vortex_user_id', 'service_user_id', unique=True),
    Index('service_vortex_links_pk', 'vortex_user_id', 'service_user_id', unique=True)
)


class Subtask(Base):
    __tablename__ = 'subtask'
    __table_args__ = (
        Index('subtask_pk', 'name', 'subtask_list_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    subtask_list_id = Column(ForeignKey('subtasks_to_task.id'), nullable=False, index=True)
    is_success = Column(Integer, nullable=False)
    value = Column(Text)
    name = Column(Text)

    subtask_list = relationship('SubtasksToTask')


class SubtasksToTask(Base):
    __tablename__ = 'subtasks_to_task'
    __table_args__ = (
        Index('subtasks_to_task_pk', 'name', 'task_id', unique=True),
    )

    task_id = Column(ForeignKey('issues.id'), nullable=False, index=True)
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)

    task = relationship('Issue')


class Tracker(Base):
    __tablename__ = 'trackers'

    id = Column(Integer, primary_key=True)
    name = Column(String(30), unique=True)


t_user_for_tg = Table(
    'user_for_tg', metadata,
    Column('login', String(50)),
    Column('tg_user_id', Integer),
    Index('user_for_tg_pk', 'login', 'tg_user_id', unique=True)
)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    login = Column(String(255))
    hashed_password = Column(String(40))
    firstname = Column(String(30))
    lastname = Column(String(255))
    admin = Column(Integer)
    status = Column(Integer)
    last_login_on = Column(DateTime)
    created_on = Column(DateTime)
    updated_on = Column(DateTime)
    type = Column(String(255))
    mail_notification = Column(String(255))
    salt = Column(String(64))
    must_change_passwd = Column(Integer)
    passwd_changed_on = Column(DateTime)
    specific_id = Column(Integer)

    favorites = relationship(
        'User',
        secondary='favorite_nfm',
        primaryjoin='User.id == favorite_nfm.c.favorite_by',
        secondaryjoin='User.id == favorite_nfm.c.favorite_id'
    )
    users = relationship(
        'User',
        secondary='groups_users',
        primaryjoin='User.id == groups_users.c.group_id',
        secondaryjoin='User.id == groups_users.c.user_id'
    )

from sqlalchemy import select

session = Session(engine)

stmt = select(User).where(User.login.in_(['a.mamij']))

for user in session.scalars(stmt):
    print(user.lastname)
