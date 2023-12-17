# Contribution guide

## Setting up the environment

```shell
$ git clone git@github.com:Saluev/suppgram.git
$ cd suppgram
$ python -m pip install -r requirements.txt
```

<br/>

## Running tests

To run all tests, you'll need a running MongoDB instance. The easiest way to get
one is by using Docker:
```shell
$ docker run -p 27107:27017 -d mongo:latest
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

## Running documentation locally

```shell
mkdocs serve
```

<br/>
