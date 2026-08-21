import os

# PyMySQL stands in for mysqlclient (no compiled dependency to install).
# Only needed when actually talking to MySQL — harmless to skip otherwise.
if os.getenv("DB_ENGINE", "mysql") == "mysql":
    import pymysql

    pymysql.install_as_MySQLdb()
