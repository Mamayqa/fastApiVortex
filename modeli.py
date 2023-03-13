from pydantic import BaseModel


class SqlModel(BaseModel):
    __table_name = ''

    def __init__(self, **data: any):
        super().__init__(**data)

    def select(self):
        sql = f"select from "
        pass

    def insert(self):
        pass

    def update(self):
        pass

    def delete(self):
        pass

    def where(self):
        pass


sql_model = SqlModel(name='test')

sql_model2 = SqlModel(name='test2')
sql_model2.select()
# print(sql_model.__test)
# print(sql_model.select(), sql_model2.select())