# Contribution guide

## Setting up the environment

```bash
$ git clone git@github.com:Saluev/suppgram.git
$ cd suppgram
$ python -m pip install -r requirements.txt
```

## Running tests

To run all tests, you'll need a running MongoDB instance. The easiest way to get
one is by using Docker:
```bash
$ docker run -p 27107:27017 -d mongo:latest
```

Then the tests can be run via `pytest`:
```shell
$ PYTHONPATH=. pytest
```
