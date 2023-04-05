import sqlparse


def format_sql(sql):
    statements = sqlparse.split(sql)
    return '\n'.join([sqlparse.format(s, reindent=True, keyword_case='upper') for s in statements])
