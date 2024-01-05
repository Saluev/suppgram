# MongoDB integration

To run Suppgram with MongoDB, you'll have to install optional dependencies:
```shell
python -m pip install "suppgram[mongodb]"
```

Then you can configure the integration by database URI. Examples:

```shell
# All-in-one CLI + MongoDB (insecure)
python -m suppgram.cli.all_in_one \
  --mongodb-uri mongodb://user:password@host:27017/database \
  ...
  
# All-in-one CLI + MongoDB (secret in environment variable)
export MONGODB_URI=mongodb://user:password@host:27017/database
python -m suppgram.cli.all_in_one ...

# All-in-one CLI + MongoDB (secret in file)
echo "mongodb://user:password@host:27017/database" > /secrets/mongodb_uri
python -m suppgram.cli.all_in_one \
  --mongodb-uri-file /secrets/mongodb_uri \
  ...
```

Suppgram will create collections with names starting with `suppgram_`, so you may use 
a preexisting database instead of creating a separate one.
