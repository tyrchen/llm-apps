import os

SCHEMAS = 'SELECT nspname AS schema_name FROM pg_catalog.pg_namespace ORDER BY nspname;'
ENUMS = '''
SELECT
  'CREATE TYPE ' || n.nspname || '.' || t.typname || ' AS ENUM (' || string_agg(quote_literal(e.enumlabel), ', ') || ');' AS sql
FROM
  pg_catalog.pg_type t
  JOIN pg_catalog.pg_namespace n ON t.typnamespace = n.oid
  JOIN pg_catalog.pg_enum e ON t.oid = e.enumtypid
WHERE
  n.nspname = '{nsp}'
  AND t.typtype = 'e'
GROUP BY
  n.nspname, t.typname;
'''
TYPES = '''
SELECT
  'CREATE TYPE ' || n.nspname || '.' || t.typname || ' AS (' || string_agg(a.attname || ' ' || pg_catalog.format_type(a.atttypid, a.atttypmod), ', ') || ');' AS sql
FROM
  pg_catalog.pg_type t
  JOIN pg_catalog.pg_namespace n ON t.typnamespace = n.oid
  JOIN pg_catalog.pg_class c ON t.typrelid = c.oid
  JOIN pg_catalog.pg_attribute a ON t.typrelid = a.attrelid
WHERE
  n.nspname = '{nsp}'
  AND t.typtype = 'c'
  AND c.relkind = 'c'
GROUP BY
  n.nspname, t.typname;
'''
TABLES = '''
WITH table_columns AS (
  SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS column_type,
    a.attnotnull AS is_not_null,
    a.attnum AS column_position
  FROM
    pg_catalog.pg_attribute a
    JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
    JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
  WHERE
    a.attnum > 0
    AND NOT a.attisdropped
    AND n.nspname = '{nsp}'
    AND c.relkind = 'r'
),
table_constraints AS (
  SELECT
    tc.constraint_name,
    tc.table_schema,
    tc.table_name,
    kcu.column_name,
    tc.constraint_type
  FROM
    information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_catalog = kcu.constraint_catalog
      AND tc.constraint_schema = kcu.constraint_schema
      AND tc.constraint_name = kcu.constraint_name
  WHERE
    tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
    AND tc.table_schema = '{nsp}'
),
formatted_columns AS (
  SELECT
    tc.schema_name,
    tc.table_name,
    tc.column_name,
    tc.column_type,
    tc.is_not_null,
    tc.column_position,
    STRING_AGG(
      tcs.constraint_type || ' (' || tc.column_name || ')',
      ', '
      ORDER BY tcs.constraint_type DESC
    ) AS column_constraints
  FROM
    table_columns tc
    LEFT JOIN table_constraints tcs
      ON tc.schema_name = tcs.table_schema
      AND tc.table_name = tcs.table_name
      AND tc.column_name = tcs.column_name
  GROUP BY
    tc.schema_name,
    tc.table_name,
    tc.column_name,
    tc.column_type,
    tc.is_not_null,
    tc.column_position
),
create_table_statements AS (
  SELECT
    fc.schema_name,
    fc.table_name,
    STRING_AGG(
      fc.column_name || ' ' || fc.column_type || (CASE WHEN fc.is_not_null THEN ' NOT NULL' ELSE '' END) || COALESCE(' ' || fc.column_constraints, ''),
      ', '
      ORDER BY fc.column_position
    ) AS formatted_columns
  FROM
    formatted_columns fc
  GROUP BY
    fc.schema_name,
    fc.table_name
)
SELECT
  'CREATE TABLE ' || schema_name || '.' || table_name || ' (' || formatted_columns || ');' AS sql
FROM
  create_table_statements;
'''
VIEWS = '''
SELECT
  'CREATE VIEW ' || n.nspname || '.' || c.relname || ' AS ' || pg_get_viewdef(c.oid) AS sql
FROM
  pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
WHERE
  c.relkind = 'v' -- Select views
  AND n.nspname = '{nsp}';
'''
MVIEWS = '''
SELECT
  'CREATE MATERIALIZED VIEW ' || n.nspname || '.' || c.relname || ' AS ' || pg_get_viewdef(c.oid) AS sql
FROM
  pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
WHERE
  c.relkind = 'm' -- Select materialized views
  AND n.nspname = '{nsp}';
'''
FUNCTIONS = '''
SELECT
  'CREATE OR REPLACE FUNCTION ' || n.nspname || '.' || p.proname || '(' || pg_get_function_arguments(p.oid) || ') RETURNS '
  || pg_get_function_result(p.oid) || ' AS $function_body$ ' || pg_get_functiondef(p.oid) || '$function_body$ LANGUAGE ' || l.lanname || ';' AS sql
FROM
  pg_catalog.pg_proc p
  JOIN pg_catalog.pg_namespace n ON p.pronamespace = n.oid
  JOIN pg_catalog.pg_language l ON p.prolang = l.oid
WHERE
  n.nspname = '{nsp}'
  AND p.prokind = 'f';
'''
INDEXES = '''
SELECT indexdef || ';' AS sql FROM pg_indexes WHERE schemaname = '{nsp}' ORDER BY tablename, indexname;
'''
TRIGGERS = '''
SELECT
  'CREATE TRIGGER ' || t.tgname
  || ' ' || CASE
    WHEN t.tgtype & 2 > 0 THEN 'BEFORE'
    WHEN t.tgtype & 4 > 0 THEN 'AFTER'
    WHEN t.tgtype & 64 > 0 THEN 'INSTEAD OF'
  END
  || ' ' || CASE
    WHEN t.tgtype & 8 > 0 THEN 'INSERT'
    WHEN t.tgtype & 16 > 0 THEN 'DELETE'
    WHEN t.tgtype & 32 > 0 THEN 'UPDATE'
  END
  || ' ON ' || n.nspname || '.' || c.relname
  || ' FOR EACH ' || CASE WHEN t.tgtype & 1 > 0 THEN 'ROW' ELSE 'STATEMENT' END
  || ' EXECUTE FUNCTION ' || np.nspname || '.' || p.proname || '();' AS sql
FROM
  pg_catalog.pg_trigger t
  JOIN pg_catalog.pg_class c ON t.tgrelid = c.oid
  JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
  JOIN pg_catalog.pg_proc p ON t.tgfoid = p.oid
  JOIN pg_catalog.pg_namespace np ON p.pronamespace = np.oid
WHERE
  n.nspname = '{nsp}'
  AND NOT t.tgisinternal;
'''


def load_from_db(con):
    '''
    Load schemas from the database.

    Arguments:
    con: A database connection.

    Returns a dictionary of schemas, keyed by schema name.
    '''
    schemas = ''
    for row in con.execute(SCHEMAS):
        if row['schema_name'].startswith('pg_') or row['schema_name'] in ['public', 'information_schema']:
            continue
        schema = row['schema_name']
        schemas += _load_schema(con, schema)
    return schemas


def load_from_file(db_name):
    '''
    Load schemas from a json file.

    Arguments:
    db_name: The name of the database.

    Returns a SQL string containing all schemas.
    '''

    path = schema_path(db_name)
    with open(path) as f:
        schemas = f.read()
        return schemas


def save_to_file(db_name, schemas):
    '''
    Save schemas to a sql file.

    Arguments:
    db_name: The name of the database.
    schemas: schema sql.
    '''

    path = schema_path(db_name)
    with open(path, 'w') as f:
        f.write(schemas)


def exists(db_name):
    '''
    Check if a schema file exists.

    Arguments:
    db_name: The name of the database.

    Returns True if the schema file exists, otherwise False.
    '''

    path = schema_path(db_name)
    return os.path.exists(path)


def schema_path(db_name):
    return f'data/db/{db_name}.sql'


def _load_schema(con, name):
    sql = f'-- Schema: {name}\n'

    items = con.execute(ENUMS.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Enums\n'
        for row in items:
            sql += row['sql'] + '\n'

    items = con.execute(TYPES.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Types\n'
        for row in items:
            sql += row['sql'] + '\n'

    items = con.execute(TABLES.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Tables\n'
        for row in items:
            sql += row['sql'] + '\n'

    items = con.execute(VIEWS.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Views\n'
        for row in items:
            sql += row['sql'] + '\n'

    items = con.execute(MVIEWS.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Materialized Views\n'
        for row in items:
            sql += row['sql'] + '\n'

    items = con.execute(FUNCTIONS.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Functions\n'
        for row in items:
            sql += row['sql'] + '\n'

    items = con.execute(INDEXES.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Indexes\n'
        for row in items:
            sql += row['sql'] + '\n'

    items = con.execute(TRIGGERS.format(nsp=name)).fetchall()
    if items:
        sql += '\n-- Triggers\n'
        for row in items:
            sql += row['sql'] + '\n'

    return sql + '\n'
