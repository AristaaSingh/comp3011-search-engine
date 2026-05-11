import logging

# Suppress all INFO/DEBUG log output during test runs so pytest output
# stays clean. WARNING and above still appear (e.g. unexpected errors).
logging.disable(logging.INFO)
