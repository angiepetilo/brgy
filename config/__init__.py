try:
    import pymysql
    pymysql.install_as_MySQLdb()
    from django.db.backends.mysql.base import DatabaseWrapper
    from django.db.backends.mysql.features import DatabaseFeatures
    # Allow local MariaDB 10.4.x (XAMPP) without version check rejection
    DatabaseWrapper.check_database_version_supported = lambda self: None
    DatabaseFeatures.can_return_columns_from_insert = False
except (ImportError, Exception):
    pass
