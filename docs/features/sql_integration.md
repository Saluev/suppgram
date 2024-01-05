# PostgreSQL/SQLite integration

Suppgram ships with support for arbitrary persistent storage supported by SQLAlchemy,
including PostgreSQL, SQLite and [numerous other databases](https://docs.sqlalchemy.org/en/20/dialects/).
However, note that unit tests are only run for PostgreSQL (latest) and SQLite.

To run Suppgram with SQLAlchemy, you'll have to install optional dependencies:
```shell
python -m pip install "suppgram[sqlalchemy]"
```
This pack of dependencies includes asynchronous drivers for PostgreSQL and SQLite. 
For other databases, additional packages may be required.

Then you can configure the integration the same way SQLAlchemy is normally configured — 
by database URI. Examples:
```shell
# All-in-one CLI + SQLite
python -m suppgram.cli.all_in_one \
    --sqlalchemy-uri sqlite+aiosqlite:///path/to/file.db \
    ...

# All-in-one CLI + PostgreSQL (insecure)
python -m suppgram.cli.all_in_one \
    --sqlalchemy-uri postgresql+asyncpg://user:password@host:5432/database \
    ...
  
# All-in-one CLI + PostgreSQL (secret in environment variable)
export SQLALCHEMY_URI=postgresql+asyncpg://user:password@host:5432/database
python -m suppgram.cli.all_in_one ...

# All-in-one CLI + PostgreSQL (secret in file)
echo "postgresql+asyncpg://user:password@host:5432/database" > /secrets/postgres_uri
python -m suppgram.cli.all_in_one \
    --sqlalchemy-uri-file /secrets/postgres_uri \
    ...
```

Suppgram will create tables with names starting with `suppgram_`, so you may use 
a preexisting database instead of creating a separate one.
