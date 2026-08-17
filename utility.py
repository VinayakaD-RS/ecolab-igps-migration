import json
import logging
import os


def get_in_batch(lst, batch_size):
    for i in range(0, len(lst), batch_size):
        yield lst[i:i + batch_size]


def ensure_dir(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def write_json(path, data):
    ensure_dir(path)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def read_json(path):
    with open(path, "r") as f:
        return json.load(f)


def setup_logging(log_file):
    ensure_dir(log_file)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )