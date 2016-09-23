# config file for running Travis with postgres
c.NotebookNotary.db_connect = 'psycopg2.connect'
c.NotebookNotary.db_connect_kwargs = dict(
    database='travis_ci_test',
)
