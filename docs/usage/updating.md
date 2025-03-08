# Updating to a newer version

Since Suppgram involves database interaction, switching to a
newer version may require running database migrations. Suppgram
uses [Alembic](https://alembic.sqlalchemy.org/en/latest/) for 
SQLAlchemy storage. As of now, MongoDB storage doesn't require 
migrations.

**Before** updating, ensure that Alembic knows the current state
of your database:
```shell
python -m alembic -c $(
  python -c "import os, suppgram; print(os.path.dirname(suppgram.__file__))"
)/alembic.ini stamp head
```

Then install newer version of Suppgram:
```shell
python -m pip install --upgrade suppgram
```

Then run migrations:
```shell
python -m alembic -c $(
  python -c "import os, suppgram; print(os.path.dirname(suppgram.__file__))"
)/alembic.ini upgrade head
```
