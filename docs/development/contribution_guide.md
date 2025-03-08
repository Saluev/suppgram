# Contribution guide

## Setting up the environment

```shell
$ git clone git@github.com:Saluev/suppgram.git
$ cd suppgram
$ python -m pip install -r requirements.txt
```

<br/>

## Running tests

To run all tests, you'll need running MongoDB and PostgreSQL instances. The easiest way to get
one is by using Docker:
```shell
$ docker run -p 27107:27017 -d mongo:latest
$ docker run -p 5432:5432 -e POSTGRES_USER=suppgram -e POSTGRES_PASSWORD=test -e POSTGRES_DB=suppgram_test -d postgres:latest
```

Then the tests can be run via `pytest`:
```shell
$ PYTHONPATH=. pytest
```

<br/>

## Running static checks

Suppgram uses mypy for type checking and ruff as a linter. Just run

```shell
mypy suppgram
ruff supppram
```

Feel free to add these commands to your pre-commit hook.

<br/>

## Working with Alembic

Your current SQLAlchemy URL must be specified in `alembic.ini` (`sqlalchemy.url` setting).

To migrate to current state of things:

```shell
python -m alembic -c suppgram/alembic.ini upgrade head
```

To create a new migration:

```shell
python -m alembic -c suppgram/alembic.ini revision --autogenerate -m "..."
```

<br/>

## Running documentation locally

```shell
mkdocs serve
```

<br/>
