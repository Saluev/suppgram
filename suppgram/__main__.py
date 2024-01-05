import sys

print(
    "Error: 'suppgram' package is not directly runnable. Did you mean 'suppgram.cli.all_in_one'?",
    file=sys.stderr,
)
sys.exit(1)
